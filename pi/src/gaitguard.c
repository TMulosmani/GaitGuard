/*
 * GaitGuard — Core pipeline implementation in C
 */
#include "gaitguard.h"

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

static float clampf(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static float sigmoidf(float x) {
    return 1.0f / (1.0f + expf(-x));
}

/* ------------------------------------------------------------------ */
/* Complementary filter                                                */
/* ------------------------------------------------------------------ */

float accel_to_angle(float ax, float az) {
    return atan2f(ax, az) * (180.0f / (float)M_PI);
}

float cf_update(CompFilter *cf, float gyro_dps, float accel_angle_deg) {
    float gyro_pred = cf->angle + gyro_dps * DT;
    cf->angle = COMP_ALPHA * gyro_pred + (1.0f - COMP_ALPHA) * accel_angle_deg;
    return cf->angle;
}

/* ------------------------------------------------------------------ */
/* Angle computer                                                      */
/* ------------------------------------------------------------------ */

void ac_init(AngleComputer *ac) {
    memset(ac, 0, sizeof(*ac));
}

void ac_set_baseline(AngleComputer *ac, float thigh, float shin, float foot) {
    ac->baseline_knee  = thigh - shin;
    ac->baseline_ankle = shin  - foot;
    ac->cf_thigh.angle = thigh;
    ac->cf_shin.angle  = shin;
    ac->cf_foot.angle  = foot;
}

void ac_update(AngleComputer *ac, const SensorPacket *pkt, float *knee, float *ankle) {
    float ta = cf_update(&ac->cf_thigh, pkt->thigh.gx,
                         accel_to_angle(pkt->thigh.ax, pkt->thigh.az));
    float sa = cf_update(&ac->cf_shin, pkt->shin.gx,
                         accel_to_angle(pkt->shin.ax, pkt->shin.az));
    float fa = cf_update(&ac->cf_foot, pkt->foot.gx,
                         accel_to_angle(pkt->foot.ax, pkt->foot.az));
    *knee  = (ta - sa) - ac->baseline_knee;
    *ankle = (sa - fa) - ac->baseline_ankle;
}

/* ------------------------------------------------------------------ */
/* Linear interpolation (resample to N points)                         */
/* ------------------------------------------------------------------ */

void interp_linear(const float *src, int src_len, float *dst, int dst_len) {
    if (src_len < 2 || dst_len < 2) {
        for (int i = 0; i < dst_len; i++) dst[i] = src_len > 0 ? src[0] : 0;
        return;
    }
    for (int i = 0; i < dst_len; i++) {
        float t = (float)i / (float)(dst_len - 1) * (float)(src_len - 1);
        int lo = (int)t;
        int hi = lo + 1;
        if (hi >= src_len) { hi = src_len - 1; lo = hi - 1; }
        float frac = t - (float)lo;
        dst[i] = src[lo] * (1.0f - frac) + src[hi] * frac;
    }
}

/* ------------------------------------------------------------------ */
/* Stride detection conditions                                         */
/* ------------------------------------------------------------------ */

static int conditions_met(const SensorPacket *pkt, float knee_deg) {
    float gx = pkt->foot.gx, gy = pkt->foot.gy, gz = pkt->foot.gz;
    float gyro_mag = sqrtf(gx*gx + gy*gy + gz*gz);
    float az_err = fabsf(fabsf(pkt->foot.az) - 1.0f);
    return (gyro_mag < OMEGA_THRESH_DPS &&
            az_err < ACCEL_Z_TOL_G &&
            fabsf(knee_deg) < KNEE_NEAR_ZERO_DEG);
}

/* ------------------------------------------------------------------ */
/* Segmenter                                                           */
/* ------------------------------------------------------------------ */

static void seg_init(Segmenter *s) {
    memset(s, 0, sizeof(*s));
    s->last_boundary_ms = -1e9f;
    s->cond_hold_start = 0;
    s->cond_hold_active = 0;
}

static void seg_confirm_boundary(Segmenter *s, float t_ms) {
    StrideBuffer *cur = &s->current;
    cur->duration_ms = t_ms - cur->start_ms;

    /* Save as last completed */
    memcpy(&s->last_completed, cur, sizeof(StrideBuffer));
    s->has_last_completed = 1;

    /* Check validity */
    if (cur->duration_ms >= MIN_STRIDE_MS && cur->duration_ms <= MAX_STRIDE_MS &&
        cur->count >= 5 && s->n_valid < MAX_PROFILE_STRIDES) {
        /* Time-normalise and store */
        NormStride *ns = &s->valid_strides[s->n_valid];
        interp_linear(cur->knee, cur->count, ns->knee, GAIT_CYCLE_PTS);
        interp_linear(cur->ankle, cur->count, ns->ankle, GAIT_CYCLE_PTS);
        s->n_valid++;
    }

    /* Reset buffer */
    cur->count = 0;
    cur->start_ms = t_ms;
    s->last_boundary_ms = t_ms;
}

/* Returns 1 if a stride boundary was just confirmed */
int seg_feed(Segmenter *s, const SensorPacket *pkt, float knee, float ankle) {
    float t = pkt->timestamp_ms;
    StrideBuffer *cur = &s->current;

    /* Accumulate */
    if (cur->count < MAX_STRIDE_SAMPLES) {
        cur->knee[cur->count] = knee;
        cur->ankle[cur->count] = ankle;
        cur->count++;
    }
    if (cur->count == 1) cur->start_ms = t;

    /* Condition check */
    int cond = conditions_met(pkt, knee);
    int in_lockout = (t - s->last_boundary_ms) < LOCKOUT_MS;

    if (cond && !in_lockout) {
        if (!s->cond_hold_active) {
            s->cond_hold_start = t;
            s->cond_hold_active = 1;
        } else if ((t - s->cond_hold_start) >= COND_HOLD_MS) {
            seg_confirm_boundary(s, t);
            s->cond_hold_active = 0;
            return 1;
        }
    } else {
        s->cond_hold_active = 0;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* LSTM inference                                                      */
/* ------------------------------------------------------------------ */

/*
 * Single LSTM layer forward pass.
 * input: (seq_len, input_size)
 * Wi: (4*hidden, input_size), Wh: (4*hidden, hidden)
 * bi, bh: (4*hidden)
 * h_out, c_out: (hidden) — final hidden/cell states
 */
static void lstm_layer(const float *input, int seq_len, int input_size,
                       const float *Wi, const float *Wh,
                       const float *bi, const float *bh,
                       float *h_out, float *c_out) {
    float h[LSTM_HIDDEN] = {0};
    float c[LSTM_HIDDEN] = {0};
    float gates[4 * LSTM_HIDDEN];

    for (int t = 0; t < seq_len; t++) {
        const float *x = input + t * input_size;

        /* gates = Wi @ x + bi + Wh @ h + bh */
        for (int g = 0; g < 4 * LSTM_HIDDEN; g++) {
            float sum = bi[g] + bh[g];
            /* Wi @ x */
            for (int j = 0; j < input_size; j++)
                sum += Wi[g * input_size + j] * x[j];
            /* Wh @ h */
            for (int j = 0; j < LSTM_HIDDEN; j++)
                sum += Wh[g * LSTM_HIDDEN + j] * h[j];
            gates[g] = sum;
        }

        /* i, f, g, o gates */
        for (int j = 0; j < LSTM_HIDDEN; j++) {
            float i_gate = sigmoidf(gates[0 * LSTM_HIDDEN + j]);
            float f_gate = sigmoidf(gates[1 * LSTM_HIDDEN + j]);
            float g_gate = tanhf(gates[2 * LSTM_HIDDEN + j]);
            float o_gate = sigmoidf(gates[3 * LSTM_HIDDEN + j]);
            c[j] = f_gate * c[j] + i_gate * g_gate;
            h[j] = o_gate * tanhf(c[j]);
        }
    }

    memcpy(h_out, h, LSTM_HIDDEN * sizeof(float));
    memcpy(c_out, c, LSTM_HIDDEN * sizeof(float));
}

void lstm_infer(const LSTMWeights *w, const float *anchor, float *output) {
    /* anchor: (ANCHOR_PTS, N_CHANNELS) = (20, 2) — already normalised */

    float h0[LSTM_HIDDEN], c0[LSTM_HIDDEN];
    float h1[LSTM_HIDDEN], c1[LSTM_HIDDEN];

    /* Layer 0: input_size = N_CHANNELS = 2 */
    lstm_layer(anchor, ANCHOR_PTS, N_CHANNELS,
               w->Wi0, w->Wh0, w->bi0, w->bh0, h0, c0);

    /* Layer 1: input_size = LSTM_HIDDEN
     * We need to pass the full sequence of h0 outputs through layer 1.
     * For simplicity with stacked LSTM, we re-run layer 0 and collect
     * intermediate h states, then feed them through layer 1. */

    /* Actually, let's do it properly: collect all h0 outputs */
    float h0_seq[ANCHOR_PTS * LSTM_HIDDEN];
    {
        float h[LSTM_HIDDEN] = {0};
        float c_tmp[LSTM_HIDDEN] = {0};
        float gates[4 * LSTM_HIDDEN];

        for (int t = 0; t < ANCHOR_PTS; t++) {
            const float *x = anchor + t * N_CHANNELS;
            for (int g = 0; g < 4 * LSTM_HIDDEN; g++) {
                float sum = w->bi0[g] + w->bh0[g];
                for (int j = 0; j < N_CHANNELS; j++)
                    sum += w->Wi0[g * N_CHANNELS + j] * x[j];
                for (int j = 0; j < LSTM_HIDDEN; j++)
                    sum += w->Wh0[g * LSTM_HIDDEN + j] * h[j];
                gates[g] = sum;
            }
            for (int j = 0; j < LSTM_HIDDEN; j++) {
                float ig = sigmoidf(gates[0 * LSTM_HIDDEN + j]);
                float fg = sigmoidf(gates[1 * LSTM_HIDDEN + j]);
                float gg = tanhf(gates[2 * LSTM_HIDDEN + j]);
                float og = sigmoidf(gates[3 * LSTM_HIDDEN + j]);
                c_tmp[j] = fg * c_tmp[j] + ig * gg;
                h[j] = og * tanhf(c_tmp[j]);
            }
            memcpy(h0_seq + t * LSTM_HIDDEN, h, LSTM_HIDDEN * sizeof(float));
        }
    }

    /* Layer 1: input is h0_seq, input_size = LSTM_HIDDEN */
    lstm_layer(h0_seq, ANCHOR_PTS, LSTM_HIDDEN,
               w->Wi1, w->Wh1, w->bi1, w->bh1, h1, c1);

    /* Linear head: output = Whead @ h1 + bhead */
    /* Whead: (PREDICT_PTS * N_CHANNELS, LSTM_HIDDEN) */
    int out_size = PREDICT_PTS * N_CHANNELS;
    for (int i = 0; i < out_size; i++) {
        float sum = w->bhead[i];
        for (int j = 0; j < LSTM_HIDDEN; j++)
            sum += w->Whead[i * LSTM_HIDDEN + j] * h1[j];
        output[i] = sum;
    }
}

/* ------------------------------------------------------------------ */
/* Scoring                                                             */
/* ------------------------------------------------------------------ */

StrideResult score_stride(const float *obs_knee, const float *obs_ankle,
                          const DigitalTwin *twin, const GaitProfile *prof,
                          int stride_num) {
    StrideResult r;
    memset(&r, 0, sizeof(r));
    r.stride_number = stride_num;
    memcpy(r.observed_knee, obs_knee, GAIT_CYCLE_PTS * sizeof(float));
    memcpy(r.observed_ankle, obs_ankle, GAIT_CYCLE_PTS * sizeof(float));

    /* Deviations (post-anchor region: indices 20-99) */
    float knee_dev[PREDICT_PTS], ankle_dev[PREDICT_PTS];
    float sum_k = 0, sum_a = 0;
    for (int i = 0; i < PREDICT_PTS; i++) {
        knee_dev[i]  = fabsf(obs_knee[ANCHOR_PTS + i]  - twin->twin_knee[ANCHOR_PTS + i]);
        ankle_dev[i] = fabsf(obs_ankle[ANCHOR_PTS + i] - twin->twin_ankle[ANCHOR_PTS + i]);
        sum_k += knee_dev[i];
        sum_a += ankle_dev[i];
    }
    float mean_k = sum_k / PREDICT_PTS;
    float mean_a = sum_a / PREDICT_PTS;

    r.z_knee  = mean_k / prof->std_knee;
    r.z_ankle = mean_a / prof->std_ankle;
    r.dev_score = r.z_knee * GHS_WEIGHT_KNEE + r.z_ankle * GHS_WEIGHT_ANKLE;
    r.ghs = clampf(100.0f - r.dev_score * GHS_SCALE, 0, 100);

    /* Haptic determination */
    r.haptic = HAPTIC_NONE;
    if (r.dev_score >= HAPTIC_THRESH_SD) {
        int hs_lo = HEEL_STRIKE_LO - ANCHOR_PTS;
        int hs_hi = HEEL_STRIKE_HI - ANCHOR_PTS;
        int sw_lo = SWING_LO - ANCHOR_PTS;
        int sw_hi = SWING_HI - ANCHOR_PTS;
        if (hs_lo < 0) hs_lo = 0;
        if (sw_lo < 0) sw_lo = 0;
        if (hs_hi > PREDICT_PTS) hs_hi = PREDICT_PTS;
        if (sw_hi > PREDICT_PTS) sw_hi = PREDICT_PTS;

        float knee_hs = 0, ankle_sw = 0;
        for (int i = hs_lo; i < hs_hi; i++) knee_hs += knee_dev[i];
        knee_hs /= (hs_hi - hs_lo);
        for (int i = sw_lo; i < sw_hi; i++) ankle_sw += ankle_dev[i];
        ankle_sw /= (sw_hi - sw_lo);

        if (knee_hs >= ankle_sw && knee_hs > 5.0f)
            r.haptic = HAPTIC_TWO_SHORT;
        else if (ankle_sw > knee_hs && ankle_sw > 5.0f)
            r.haptic = HAPTIC_ONE_LONG;
        else
            r.haptic = HAPTIC_THREE_SHORT;
    }

    /* Color */
    if (r.ghs >= 80) r.color = "green";
    else if (r.ghs >= 50) r.color = "yellow";
    else r.color = "red";

    return r;
}

/* ------------------------------------------------------------------ */
/* Pipeline                                                            */
/* ------------------------------------------------------------------ */

void pipeline_init(Pipeline *p) {
    memset(p, 0, sizeof(*p));
    p->state = STATE_CALIBRATION;
    ac_init(&p->angles);
    seg_init(&p->seg);
}

int pipeline_load_lstm(Pipeline *p, const char *weights_path) {
    FILE *f = fopen(weights_path, "rb");
    if (!f) {
        fprintf(stderr, "[Pipeline] Cannot open LSTM weights: %s\n", weights_path);
        return -1;
    }

    LSTMWeights *w = &p->lstm;

    /* Read in the same order as export_weights.py writes them */
    size_t n = 0;
    n += fread(w->Wi0, sizeof(float), 4 * LSTM_HIDDEN * N_CHANNELS, f);
    n += fread(w->Wh0, sizeof(float), 4 * LSTM_HIDDEN * LSTM_HIDDEN, f);
    n += fread(w->bi0, sizeof(float), 4 * LSTM_HIDDEN, f);
    n += fread(w->bh0, sizeof(float), 4 * LSTM_HIDDEN, f);
    n += fread(w->Wi1, sizeof(float), 4 * LSTM_HIDDEN * LSTM_HIDDEN, f);
    n += fread(w->Wh1, sizeof(float), 4 * LSTM_HIDDEN * LSTM_HIDDEN, f);
    n += fread(w->bi1, sizeof(float), 4 * LSTM_HIDDEN, f);
    n += fread(w->bh1, sizeof(float), 4 * LSTM_HIDDEN, f);
    n += fread(w->Whead, sizeof(float), PREDICT_PTS * N_CHANNELS * LSTM_HIDDEN, f);
    n += fread(w->bhead, sizeof(float), PREDICT_PTS * N_CHANNELS, f);
    n += fread(w->norm_mean, sizeof(float), N_CHANNELS, f);
    n += fread(w->norm_std, sizeof(float), N_CHANNELS, f);

    fclose(f);

    size_t expected = 4*LSTM_HIDDEN*N_CHANNELS + 4*LSTM_HIDDEN*LSTM_HIDDEN + 4*LSTM_HIDDEN + 4*LSTM_HIDDEN
                    + 4*LSTM_HIDDEN*LSTM_HIDDEN + 4*LSTM_HIDDEN*LSTM_HIDDEN + 4*LSTM_HIDDEN + 4*LSTM_HIDDEN
                    + PREDICT_PTS*N_CHANNELS*LSTM_HIDDEN + PREDICT_PTS*N_CHANNELS
                    + N_CHANNELS + N_CHANNELS;
    if (n != expected) {
        fprintf(stderr, "[Pipeline] Weight file size mismatch: read %zu, expected %zu\n", n, expected);
        return -1;
    }

    w->loaded = 1;
    printf("[Pipeline] LSTM weights loaded from %s\n", weights_path);
    printf("[Pipeline] Norm stats: knee mu=%.2f sd=%.2f | ankle mu=%.2f sd=%.2f\n",
           w->norm_mean[0], w->norm_std[0], w->norm_mean[1], w->norm_std[1]);
    return 0;
}

void build_profile(Pipeline *p) {
    GaitProfile *prof = &p->profile;
    Segmenter *s = &p->seg;

    memset(prof, 0, sizeof(*prof));
    prof->n_strides = s->n_valid;

    /* Compute mean curves */
    for (int i = 0; i < GAIT_CYCLE_PTS; i++) {
        float sk = 0, sa = 0;
        for (int j = 0; j < s->n_valid; j++) {
            sk += s->valid_strides[j].knee[i];
            sa += s->valid_strides[j].ankle[i];
        }
        prof->mean_knee[i]  = sk / s->n_valid;
        prof->mean_ankle[i] = sa / s->n_valid;
    }

    /* Compute stride-to-stride SD */
    float var_k = 0, var_a = 0;
    for (int i = 0; i < GAIT_CYCLE_PTS; i++) {
        float vk = 0, va = 0;
        for (int j = 0; j < s->n_valid; j++) {
            float dk = s->valid_strides[j].knee[i] - prof->mean_knee[i];
            float da = s->valid_strides[j].ankle[i] - prof->mean_ankle[i];
            vk += dk * dk;
            va += da * da;
        }
        var_k += sqrtf(vk / s->n_valid);
        var_a += sqrtf(va / s->n_valid);
    }
    prof->std_knee  = fmaxf(var_k / GAIT_CYCLE_PTS, 1e-3f);
    prof->std_ankle = fmaxf(var_a / GAIT_CYCLE_PTS, 1e-3f);

    /* Anchor segments */
    memcpy(prof->anchor_knee, prof->mean_knee, ANCHOR_PTS * sizeof(float));
    memcpy(prof->anchor_ankle, prof->mean_ankle, ANCHOR_PTS * sizeof(float));
}

void generate_twin(Pipeline *p) {
    LSTMWeights *w = &p->lstm;
    GaitProfile *prof = &p->profile;
    DigitalTwin *twin = &p->twin;

    if (!w->loaded) {
        /* Fallback: use mean curves as twin */
        printf("[Pipeline] WARNING: No LSTM weights, using mean curves as twin\n");
        memcpy(twin->twin_knee, prof->mean_knee, GAIT_CYCLE_PTS * sizeof(float));
        memcpy(twin->twin_ankle, prof->mean_ankle, GAIT_CYCLE_PTS * sizeof(float));
        return;
    }

    /* Prepare normalised anchor input: (20, 2) */
    float anchor_norm[ANCHOR_PTS * N_CHANNELS];
    for (int i = 0; i < ANCHOR_PTS; i++) {
        anchor_norm[i * 2 + 0] = (prof->anchor_knee[i]  - w->norm_mean[0]) / w->norm_std[0];
        anchor_norm[i * 2 + 1] = (prof->anchor_ankle[i] - w->norm_mean[1]) / w->norm_std[1];
    }

    /* LSTM inference → (80 * 2) output */
    float pred_norm[PREDICT_PTS * N_CHANNELS];
    lstm_infer(w, anchor_norm, pred_norm);

    /* Denormalise */
    float pred_knee[PREDICT_PTS], pred_ankle[PREDICT_PTS];
    for (int i = 0; i < PREDICT_PTS; i++) {
        pred_knee[i]  = pred_norm[i * 2 + 0] * w->norm_std[0] + w->norm_mean[0];
        pred_ankle[i] = pred_norm[i * 2 + 1] * w->norm_std[1] + w->norm_mean[1];
    }

    /* Boundary blend (5 points) */
    float anchor_end_k = prof->anchor_knee[ANCHOR_PTS - 1];
    float anchor_end_a = prof->anchor_ankle[ANCHOR_PTS - 1];
    for (int i = 0; i < 5; i++) {
        float alpha = (float)(i + 1) / 6.0f;
        pred_knee[i]  = (1.0f - alpha) * anchor_end_k + alpha * pred_knee[i];
        pred_ankle[i] = (1.0f - alpha) * anchor_end_a + alpha * pred_ankle[i];
    }

    /* Concatenate anchor + prediction */
    memcpy(twin->twin_knee, prof->anchor_knee, ANCHOR_PTS * sizeof(float));
    memcpy(twin->twin_knee + ANCHOR_PTS, pred_knee, PREDICT_PTS * sizeof(float));
    memcpy(twin->twin_ankle, prof->anchor_ankle, ANCHOR_PTS * sizeof(float));
    memcpy(twin->twin_ankle + ANCHOR_PTS, pred_ankle, PREDICT_PTS * sizeof(float));

    printf("[Pipeline] Digital twin generated via LSTM\n");
}

/* Static result buffer (returned by pipeline_step) */
static StrideResult s_result;
static int s_has_result;

StrideResult *pipeline_step(Pipeline *p, const SensorPacket *pkt) {
    s_has_result = 0;

    if (p->state == STATE_CALIBRATION) {
        int i = p->calib_count;
        if (i < CALIB_SAMPLES) {
            p->calib_thigh[i] = accel_to_angle(pkt->thigh.ax, pkt->thigh.az);
            p->calib_shin[i]  = accel_to_angle(pkt->shin.ax, pkt->shin.az);
            p->calib_foot[i]  = accel_to_angle(pkt->foot.ax, pkt->foot.az);
            p->calib_count++;

            if (p->calib_count >= CALIB_SAMPLES) {
                float mt = 0, ms = 0, mf = 0;
                for (int j = 0; j < CALIB_SAMPLES; j++) {
                    mt += p->calib_thigh[j];
                    ms += p->calib_shin[j];
                    mf += p->calib_foot[j];
                }
                mt /= CALIB_SAMPLES; ms /= CALIB_SAMPLES; mf /= CALIB_SAMPLES;
                ac_set_baseline(&p->angles, mt, ms, mf);
                p->state = STATE_SEGMENTATION;
                printf("[Pipeline] Calibrated. Baselines: thigh=%.1f shin=%.1f foot=%.1f\n", mt, ms, mf);
            }
        }
        return NULL;
    }

    /* Compute joint angles */
    float knee, ankle;
    ac_update(&p->angles, pkt, &knee, &ankle);

    if (p->state == STATE_SEGMENTATION) {
        seg_feed(&p->seg, pkt, knee, ankle);

        if (p->seg.n_valid >= MIN_STRIDES_PROFILE) {
            printf("[Pipeline] %d valid strides collected. Building profile...\n", p->seg.n_valid);
            build_profile(p);
            p->state = STATE_TWIN_GENERATION;
            generate_twin(p);
            p->state = STATE_MONITORING;
            printf("[Pipeline] Monitoring active.\n");
            /* Reset segmenter for monitoring phase */
            seg_init(&p->seg);
        }
        return NULL;
    }

    if (p->state == STATE_MONITORING) {
        if (seg_feed(&p->seg, pkt, knee, ankle)) {
            StrideBuffer *sb = &p->seg.last_completed;
            if (sb->count >= 5) {
                float obs_k[GAIT_CYCLE_PTS], obs_a[GAIT_CYCLE_PTS];
                interp_linear(sb->knee, sb->count, obs_k, GAIT_CYCLE_PTS);
                interp_linear(sb->ankle, sb->count, obs_a, GAIT_CYCLE_PTS);

                p->stride_count++;
                s_result = score_stride(obs_k, obs_a, &p->twin, &p->profile, p->stride_count);
                s_has_result = 1;
                return &s_result;
            }
        }
    }

    return NULL;
}

/* ------------------------------------------------------------------ */
/* UDP packet parsing                                                  */
/* ------------------------------------------------------------------ */

/* MPU-6050 scale: ±4g = 8192 LSB/g, ±500°/s = 65.5 LSB/(°/s) */
#define ACCEL_SCALE_MPU 8192.0f
#define GYRO_SCALE_MPU  65.5f
/* QMI8658: ±4g = 8192 LSB/g, ±512°/s = 64.0 LSB/(°/s) */
#define ACCEL_SCALE_QMI 8192.0f
#define GYRO_SCALE_QMI  64.0f

static int16_t read_be16(const uint8_t *p) {
    return (int16_t)((p[0] << 8) | p[1]);
}

static void parse_imu_block(const uint8_t *data, int offset, IMURaw *imu,
                            float ascale, float gscale) {
    imu->ax = read_be16(data + offset + 0) / ascale;
    imu->ay = read_be16(data + offset + 2) / ascale;
    imu->az = read_be16(data + offset + 4) / ascale;
    imu->gx = read_be16(data + offset + 6) / gscale;
    imu->gy = read_be16(data + offset + 8) / gscale;
    imu->gz = read_be16(data + offset + 10) / gscale;
}

void parse_thigh_shin(const uint8_t *data, float ts_ms, SensorPacket *pkt) {
    parse_imu_block(data, 3, &pkt->thigh, ACCEL_SCALE_MPU, GYRO_SCALE_MPU);
    parse_imu_block(data, 15, &pkt->shin, ACCEL_SCALE_MPU, GYRO_SCALE_MPU);
    pkt->timestamp_ms = ts_ms;
}

void parse_foot(const uint8_t *data, float ts_ms __attribute__((unused)), IMURaw *foot) {
    parse_imu_block(data, 3, foot, ACCEL_SCALE_QMI, GYRO_SCALE_QMI);
}
