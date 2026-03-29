/*
 * GaitGuard — Pure C pipeline for QNX / Raspberry Pi
 *
 * Implements the full 4-phase gait analysis pipeline:
 *   Phase 0: Calibration (stand still, compute baseline angles)
 *   Phase 1: Segmentation (detect strides, build gait profile)
 *   Phase 2: Digital Twin (LSTM inference from exported weights)
 *   Phase 3: Monitoring (score strides, trigger haptics)
 */
#ifndef GAITGUARD_H
#define GAITGUARD_H

#include <math.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

#define SAMPLE_RATE_HZ      50.0f
#define DT                  (1.0f / SAMPLE_RATE_HZ)
#define COMP_ALPHA          0.98f

#define CALIB_DURATION_S    2.0f
#define CALIB_SAMPLES       100  /* 2.0s * 50Hz */

#define MIN_STRIDES_PROFILE 20
#define GAIT_CYCLE_PTS      100
#define ANCHOR_PTS          20
#define PREDICT_PTS         80
#define N_CHANNELS          2   /* knee + ankle */

/* Stride detection thresholds */
#define OMEGA_THRESH_DPS    15.0f
#define ACCEL_Z_TOL_G       0.15f
#define KNEE_NEAR_ZERO_DEG  15.0f
#define COND_HOLD_MS        80.0f
#define LOCKOUT_MS          300.0f
#define MIN_STRIDE_MS       400.0f
#define MAX_STRIDE_MS       2500.0f

/* Scoring */
#define GHS_WEIGHT_KNEE     0.6f
#define GHS_WEIGHT_ANKLE    0.4f
#define GHS_SCALE           25.0f
#define HAPTIC_THRESH_SD    2.0f
#define HEEL_STRIKE_LO      21
#define HEEL_STRIKE_HI      35
#define SWING_LO            60
#define SWING_HI            85

/* LSTM architecture */
#define LSTM_HIDDEN          64
#define LSTM_LAYERS          2

/* Max samples per stride buffer */
#define MAX_STRIDE_SAMPLES  256

/* Max valid strides stored for profile */
#define MAX_PROFILE_STRIDES 80

/* UDP ports */
#define PORT_IMU_THIGH_SHIN 5001
#define PORT_IMU_FOOT       5002
#define PORT_HAPTIC_CMD     5003
#define PORT_DISPLAY_CMD    5004

/* Device IDs */
#define DEVICE_ID_THIGH_SHIN 0x01
#define DEVICE_ID_FOOT       0x02

/* Haptic patterns */
typedef enum {
    HAPTIC_NONE        = 0,
    HAPTIC_TWO_SHORT   = 1,
    HAPTIC_ONE_LONG    = 2,
    HAPTIC_THREE_SHORT = 3,
} HapticPattern;

/* Pipeline states */
typedef enum {
    STATE_CALIBRATION,
    STATE_SEGMENTATION,
    STATE_TWIN_GENERATION,
    STATE_MONITORING,
} PipelineState;

/* ------------------------------------------------------------------ */
/* Data types                                                          */
/* ------------------------------------------------------------------ */

typedef struct {
    float ax, ay, az;   /* g */
    float gx, gy, gz;   /* deg/s */
} IMURaw;

typedef struct {
    IMURaw thigh;
    IMURaw shin;
    IMURaw foot;
    float  timestamp_ms;
} SensorPacket;

/* Complementary filter state */
typedef struct {
    float angle;
} CompFilter;

/* Joint angle computer */
typedef struct {
    CompFilter cf_thigh, cf_shin, cf_foot;
    float baseline_knee;
    float baseline_ankle;
} AngleComputer;

/* Stride buffer */
typedef struct {
    float knee[MAX_STRIDE_SAMPLES];
    float ankle[MAX_STRIDE_SAMPLES];
    int   count;
    float start_ms;
    float duration_ms;
} StrideBuffer;

/* Normalised stride (100 points) */
typedef struct {
    float knee[GAIT_CYCLE_PTS];
    float ankle[GAIT_CYCLE_PTS];
} NormStride;

/* Gait profile */
typedef struct {
    float mean_knee[GAIT_CYCLE_PTS];
    float mean_ankle[GAIT_CYCLE_PTS];
    float std_knee;
    float std_ankle;
    float anchor_knee[ANCHOR_PTS];
    float anchor_ankle[ANCHOR_PTS];
    int   n_strides;
} GaitProfile;

/* Digital twin */
typedef struct {
    float twin_knee[GAIT_CYCLE_PTS];
    float twin_ankle[GAIT_CYCLE_PTS];
} DigitalTwin;

/* Stride result */
typedef struct {
    float ghs;
    float dev_score;
    float z_knee, z_ankle;
    HapticPattern haptic;
    int stride_number;
    float observed_knee[GAIT_CYCLE_PTS];
    float observed_ankle[GAIT_CYCLE_PTS];
    const char *color;  /* "green", "yellow", "red" */
} StrideResult;

/* LSTM weights (loaded from file) */
typedef struct {
    /* Layer 0 */
    float Wi0[4 * LSTM_HIDDEN * N_CHANNELS];     /* input weights */
    float Wh0[4 * LSTM_HIDDEN * LSTM_HIDDEN];     /* hidden weights */
    float bi0[4 * LSTM_HIDDEN];                    /* input bias */
    float bh0[4 * LSTM_HIDDEN];                    /* hidden bias */
    /* Layer 1 */
    float Wi1[4 * LSTM_HIDDEN * LSTM_HIDDEN];
    float Wh1[4 * LSTM_HIDDEN * LSTM_HIDDEN];
    float bi1[4 * LSTM_HIDDEN];
    float bh1[4 * LSTM_HIDDEN];
    /* Linear head */
    float Whead[PREDICT_PTS * N_CHANNELS * LSTM_HIDDEN];
    float bhead[PREDICT_PTS * N_CHANNELS];
    /* Normalisation stats */
    float norm_mean[N_CHANNELS];
    float norm_std[N_CHANNELS];
    int   loaded;
} LSTMWeights;

/* Segmenter state */
typedef struct {
    StrideBuffer current;
    float cond_hold_start;
    float last_boundary_ms;
    int   cond_hold_active;

    /* Completed valid strides for profile building */
    NormStride valid_strides[MAX_PROFILE_STRIDES];
    int        n_valid;

    /* Last completed stride for Phase 3 */
    StrideBuffer last_completed;
    int          has_last_completed;
} Segmenter;

/* Full pipeline state */
typedef struct {
    PipelineState state;
    AngleComputer angles;
    Segmenter     seg;
    GaitProfile   profile;
    DigitalTwin   twin;
    LSTMWeights   lstm;
    int           stride_count;

    /* Calibration accumulators */
    float calib_thigh[CALIB_SAMPLES];
    float calib_shin[CALIB_SAMPLES];
    float calib_foot[CALIB_SAMPLES];
    int   calib_count;
} Pipeline;

/* ------------------------------------------------------------------ */
/* Function declarations                                               */
/* ------------------------------------------------------------------ */

/* Complementary filter */
float cf_update(CompFilter *cf, float gyro_dps, float accel_angle_deg);
float accel_to_angle(float ax, float az);

/* Angle computer */
void  ac_init(AngleComputer *ac);
void  ac_set_baseline(AngleComputer *ac, float thigh, float shin, float foot);
void  ac_update(AngleComputer *ac, const SensorPacket *pkt, float *knee, float *ankle);

/* Interpolation */
void  interp_linear(const float *src, int src_len, float *dst, int dst_len);

/* Pipeline */
void  pipeline_init(Pipeline *p);
int   pipeline_load_lstm(Pipeline *p, const char *weights_path);
StrideResult *pipeline_step(Pipeline *p, const SensorPacket *pkt);

/* LSTM inference */
void  lstm_infer(const LSTMWeights *w, const float *anchor, float *output);

/* Scoring */
StrideResult score_stride(const float *obs_knee, const float *obs_ankle,
                          const DigitalTwin *twin, const GaitProfile *prof,
                          int stride_num);

/* Profile building & twin generation (called from main for record mode) */
void  build_profile(Pipeline *p);
void  generate_twin(Pipeline *p);

/* Segmenter (exposed for test mode direct use) */
int   seg_feed(Segmenter *s, const SensorPacket *pkt, float knee, float ankle);

/* UDP packet parsing */
void  parse_thigh_shin(const uint8_t *data, float ts_ms, SensorPacket *pkt);
void  parse_foot(const uint8_t *data, float ts_ms, IMURaw *foot);

#endif /* GAITGUARD_H */
