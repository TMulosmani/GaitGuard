/*
 * GaitGuard — Main entry point for QNX / Raspberry Pi
 *
 * Two modes:
 *   ./gaitguard record [weights.bin]   — Record healthy gait, save profile
 *   ./gaitguard test   [weights.bin]   — Load profile, test patient gait
 *
 * Writes JSON status to /tmp/gaitguard_status.json and stride data to
 * /tmp/gaitguard_strides.json for the web dashboard.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <time.h>

#include "gaitguard.h"

/* ------------------------------------------------------------------ */
/* Mode                                                                */
/* ------------------------------------------------------------------ */
typedef enum { MODE_RECORD, MODE_TEST } RunMode;

static volatile int running = 1;
static RunMode run_mode = MODE_TEST;

static void handle_sigint(int sig) {
    (void)sig;
    running = 0;
}

/* ------------------------------------------------------------------ */
/* ESP IP tracking                                                     */
/* ------------------------------------------------------------------ */
static struct sockaddr_in esp1_addr;
static struct sockaddr_in esp2_addr;
static int esp1_known = 0;
static int esp2_known = 0;
static int cmd_sock = -1;
static char esp1_ip_str[INET_ADDRSTRLEN] = "";
static char esp2_ip_str[INET_ADDRSTRLEN] = "";

/* ------------------------------------------------------------------ */
/* Latest foot reading                                                 */
/* ------------------------------------------------------------------ */
static IMURaw latest_foot = {0, 0, 1.0f, 0, 0, 0};
static pthread_mutex_t foot_lock = PTHREAD_MUTEX_INITIALIZER;
static volatile int foot_pkt_counter = 0;

/* ------------------------------------------------------------------ */
/* Profile save/load paths                                             */
/* ------------------------------------------------------------------ */
#define PROFILE_PATH "profile.bin"

/* ------------------------------------------------------------------ */
/* JSON status for web dashboard                                       */
/* ------------------------------------------------------------------ */
#define STATUS_PATH  "/tmp/gaitguard_status.json"
#define STRIDES_PATH "/tmp/gaitguard_strides.json"

#define MAX_STRIDE_HISTORY 200

static StrideResult stride_history[MAX_STRIDE_HISTORY];
static int stride_history_count = 0;

static void write_status_json(const Pipeline *p, const char *state_str) {
    FILE *f = fopen(STATUS_PATH, "w");
    if (!f) return;

    float ghs = 0;
    const char *color = "green";
    const char *haptic = "none";
    if (stride_history_count > 0) {
        StrideResult *last = &stride_history[stride_history_count - 1];
        ghs = last->ghs;
        color = last->color;
        switch (last->haptic) {
            case HAPTIC_TWO_SHORT:   haptic = "two_short"; break;
            case HAPTIC_ONE_LONG:    haptic = "one_long"; break;
            case HAPTIC_THREE_SHORT: haptic = "three_short"; break;
            default: break;
        }
    }

    float calib_progress = 0;
    if (p->state == STATE_CALIBRATION)
        calib_progress = (float)p->calib_count / CALIB_SAMPLES;
    else
        calib_progress = 1.0f;

    fprintf(f,
        "{\n"
        "  \"state\": \"%s\",\n"
        "  \"mode\": \"%s\",\n"
        "  \"esp1_connected\": %s,\n"
        "  \"esp2_connected\": %s,\n"
        "  \"esp1_ip\": \"%s\",\n"
        "  \"esp2_ip\": \"%s\",\n"
        "  \"stride_count\": %d,\n"
        "  \"calibration_progress\": %.2f,\n"
        "  \"current_ghs\": %.1f,\n"
        "  \"current_color\": \"%s\",\n"
        "  \"last_haptic\": \"%s\",\n"
        "  \"profile_strides\": %d\n"
        "}\n",
        state_str,
        run_mode == MODE_RECORD ? "record" : "test",
        esp1_known ? "true" : "false",
        esp2_known ? "true" : "false",
        esp1_ip_str,
        esp2_ip_str,
        stride_history_count,
        calib_progress,
        ghs,
        color,
        haptic,
        p->seg.n_valid
    );
    fclose(f);
}

static void write_strides_json(void) {
    FILE *f = fopen(STRIDES_PATH, "w");
    if (!f) return;

    fprintf(f, "{\"strides\":[\n");
    for (int i = 0; i < stride_history_count; i++) {
        StrideResult *r = &stride_history[i];
        const char *haptic = "none";
        switch (r->haptic) {
            case HAPTIC_TWO_SHORT:   haptic = "two_short"; break;
            case HAPTIC_ONE_LONG:    haptic = "one_long"; break;
            case HAPTIC_THREE_SHORT: haptic = "three_short"; break;
            default: break;
        }
        fprintf(f, "  {\"num\":%d,\"ghs\":%.1f,\"color\":\"%s\",\"haptic\":\"%s\","
                   "\"z_knee\":%.2f,\"z_ankle\":%.2f}%s\n",
                r->stride_number, r->ghs, r->color, haptic,
                r->z_knee, r->z_ankle,
                (i < stride_history_count - 1) ? "," : "");
    }
    fprintf(f, "]}\n");
    fclose(f);
}

static void add_stride_result(const StrideResult *r) {
    if (stride_history_count < MAX_STRIDE_HISTORY) {
        stride_history[stride_history_count++] = *r;
    }
    write_strides_json();
}

/* ------------------------------------------------------------------ */
/* Profile save/load                                                   */
/* ------------------------------------------------------------------ */

static int save_profile(const GaitProfile *prof, const DigitalTwin *twin, const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        perror("save_profile");
        return -1;
    }
    fwrite(prof, sizeof(GaitProfile), 1, f);
    fwrite(twin, sizeof(DigitalTwin), 1, f);
    fclose(f);
    printf("[Profile] Saved %d strides to %s\n", prof->n_strides, path);
    return 0;
}

static int load_profile(GaitProfile *prof, DigitalTwin *twin, const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "[Profile] Cannot open %s\n", path);
        return -1;
    }
    size_t n = 0;
    n += fread(prof, sizeof(GaitProfile), 1, f);
    n += fread(twin, sizeof(DigitalTwin), 1, f);
    fclose(f);
    if (n != 2) {
        fprintf(stderr, "[Profile] Invalid profile file\n");
        return -1;
    }
    printf("[Profile] Loaded %d-stride profile from %s\n", prof->n_strides, path);
    return 0;
}

/* ------------------------------------------------------------------ */
/* Send commands to ESPs                                               */
/* ------------------------------------------------------------------ */

static void send_haptic(HapticPattern pat) {
    if (!esp1_known || pat == HAPTIC_NONE) return;
    uint8_t buf[2] = {(uint8_t)pat, 0xFF};
    struct sockaddr_in addr = esp1_addr;
    addr.sin_port = htons(PORT_HAPTIC_CMD);
    sendto(cmd_sock, buf, 2, 0, (struct sockaddr *)&addr, sizeof(addr));
}

static void send_display(float score, int color, int state) {
    if (!esp2_known) return;
    uint16_t score_int = (uint16_t)(score * 10);
    uint8_t buf[6];
    buf[0] = 1;
    buf[1] = (score_int >> 8) & 0xFF;
    buf[2] = score_int & 0xFF;
    buf[3] = (uint8_t)color;
    buf[4] = (uint8_t)state;
    buf[5] = 0;
    struct sockaddr_in addr = esp2_addr;
    addr.sin_port = htons(PORT_DISPLAY_CMD);
    sendto(cmd_sock, buf, 6, 0, (struct sockaddr *)&addr, sizeof(addr));
}

/* ------------------------------------------------------------------ */
/* Console output                                                      */
/* ------------------------------------------------------------------ */
static void print_result(const StrideResult *r) {
    int bar_len = 20;
    int filled = (int)(r->ghs / 100.0f * bar_len);
    char bar[21];
    for (int i = 0; i < bar_len; i++)
        bar[i] = (i < filled) ? '#' : '.';
    bar[bar_len] = '\0';

    const char *haptic_str = "";
    switch (r->haptic) {
        case HAPTIC_TWO_SHORT:   haptic_str = "  haptic=two_short"; break;
        case HAPTIC_ONE_LONG:    haptic_str = "  haptic=one_long"; break;
        case HAPTIC_THREE_SHORT: haptic_str = "  haptic=three_short"; break;
        default: break;
    }

    printf("  Stride %3d  GHS=%5.1f  [%s]%s\n",
           r->stride_number, r->ghs, bar, haptic_str);
}

/* ------------------------------------------------------------------ */
/* Foot receiver thread                                                */
/* ------------------------------------------------------------------ */
static void *foot_thread(void *arg) {
    int sock = *(int *)arg;
    uint8_t buf[64];
    struct sockaddr_in from;
    socklen_t fromlen;

    while (running) {
        fromlen = sizeof(from);
        ssize_t n = recvfrom(sock, buf, sizeof(buf), 0,
                             (struct sockaddr *)&from, &fromlen);
        if (n < 15) continue;
        if (buf[0] != DEVICE_ID_FOOT) continue;

        if (!esp2_known) {
            esp2_addr = from;
            esp2_known = 1;
            inet_ntop(AF_INET, &from.sin_addr, esp2_ip_str, sizeof(esp2_ip_str));
            printf("[Main] ESP#2 (foot) connected from %s\n", esp2_ip_str);
        }

        IMURaw foot;
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        float ts_ms = ts.tv_sec * 1000.0f + ts.tv_nsec / 1e6f;
        parse_foot(buf, ts_ms, &foot);

        pthread_mutex_lock(&foot_lock);
        latest_foot = foot;
        foot_pkt_counter++;
        pthread_mutex_unlock(&foot_lock);
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */
int main(int argc, char **argv) {
    /* Parse args */
    const char *weights_path = "weights.bin";

    if (argc < 2) {
        fprintf(stderr, "Usage:\n");
        fprintf(stderr, "  %s record [weights.bin]   — Record healthy gait\n", argv[0]);
        fprintf(stderr, "  %s test   [weights.bin]   — Test patient gait\n", argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "record") == 0) {
        run_mode = MODE_RECORD;
    } else if (strcmp(argv[1], "test") == 0) {
        run_mode = MODE_TEST;
    } else {
        fprintf(stderr, "Unknown mode: %s (use 'record' or 'test')\n", argv[1]);
        return 1;
    }

    if (argc >= 3) weights_path = argv[2];

    signal(SIGINT, handle_sigint);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    /* Init pipeline */
    Pipeline pipeline;
    pipeline_init(&pipeline);

    if (pipeline_load_lstm(&pipeline, weights_path) != 0) {
        printf("[Main] WARNING: Running without LSTM weights\n");
    }

    /* In test mode, load saved profile + twin and skip to monitoring */
    if (run_mode == MODE_TEST) {
        if (load_profile(&pipeline.profile, &pipeline.twin, PROFILE_PATH) == 0) {
            /* Skip calibration/segmentation — go straight to calibration then monitor */
            printf("[Main] TEST MODE — Will calibrate then monitor against saved profile\n");
        } else {
            fprintf(stderr, "[Main] No saved profile found. Run in 'record' mode first.\n");
            return 1;
        }
    } else {
        printf("[Main] RECORD MODE — Walk to record healthy gait\n");
        printf("[Main] Press Ctrl+C when done walking to save profile\n");
    }

    /* Create UDP sockets */
    int sock1 = socket(AF_INET, SOCK_DGRAM, 0);
    int sock2 = socket(AF_INET, SOCK_DGRAM, 0);
    cmd_sock  = socket(AF_INET, SOCK_DGRAM, 0);

    int optval = 1;
    setsockopt(sock1, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));
    setsockopt(sock2, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));
#ifdef SO_REUSEPORT
    setsockopt(sock1, SOL_SOCKET, SO_REUSEPORT, &optval, sizeof(optval));
    setsockopt(sock2, SOL_SOCKET, SO_REUSEPORT, &optval, sizeof(optval));
#endif

    struct sockaddr_in addr1 = {0}, addr2 = {0};
    addr1.sin_family = AF_INET;
    addr1.sin_port = htons(PORT_IMU_THIGH_SHIN);
    addr1.sin_addr.s_addr = INADDR_ANY;
    addr2.sin_family = AF_INET;
    addr2.sin_port = htons(PORT_IMU_FOOT);
    addr2.sin_addr.s_addr = INADDR_ANY;

    if (bind(sock1, (struct sockaddr *)&addr1, sizeof(addr1)) < 0) {
        perror("bind port 5001");
        return 1;
    }
    if (bind(sock2, (struct sockaddr *)&addr2, sizeof(addr2)) < 0) {
        perror("bind port 5002");
        return 1;
    }

    struct timeval tv = {0, 200000};
    setsockopt(sock1, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock2, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    pthread_t foot_tid;
    pthread_create(&foot_tid, NULL, foot_thread, &sock2);

    printf("\n=== GaitGuard Pipeline (C) — %s mode ===\n",
           run_mode == MODE_RECORD ? "RECORD" : "TEST");
    printf("Listening on UDP :%d and :%d\n", PORT_IMU_THIGH_SHIN, PORT_IMU_FOOT);
    printf("Waiting for sensor data...\n\n");

    /* Init JSON status */
    write_status_json(&pipeline, "WAITING");
    write_strides_json();

    int calibration_display_sent = 0;
    struct timespec start_ts;
    clock_gettime(CLOCK_MONOTONIC, &start_ts);
    float start_ms = start_ts.tv_sec * 1000.0f + start_ts.tv_nsec / 1e6f;

    int status_counter = 0;
    int esp1_miss_count = 0;
    int esp2_miss_count = 0;
    int last_foot_counter = 0;
    #define DISCONNECT_MISSES 50  /* 50 * 200ms timeout = 10 seconds */

    /* Main loop */
    while (running) {
        uint8_t buf[64];
        struct sockaddr_in from;
        socklen_t fromlen = sizeof(from);

        ssize_t n = recvfrom(sock1, buf, sizeof(buf), 0,
                             (struct sockaddr *)&from, &fromlen);

        /* Check foot ESP liveness via packet counter */
        pthread_mutex_lock(&foot_lock);
        int cur_foot = foot_pkt_counter;
        pthread_mutex_unlock(&foot_lock);

        if (esp2_known) {
            if (cur_foot == last_foot_counter)
                esp2_miss_count++;
            else
                esp2_miss_count = 0;
            last_foot_counter = cur_foot;
            if (esp2_miss_count > DISCONNECT_MISSES) {
                esp2_known = 0;
                esp2_ip_str[0] = '\0';
                printf("[Main] ESP#2 disconnected\n");
            }
        } else if (cur_foot != last_foot_counter) {
            last_foot_counter = cur_foot;
        }

        if (n < 27) {
            /* No ESP#1 packet this cycle */
            if (esp1_known) {
                esp1_miss_count++;
                if (esp1_miss_count > DISCONNECT_MISSES) {
                    esp1_known = 0;
                    esp1_ip_str[0] = '\0';
                    printf("[Main] ESP#1 disconnected\n");
                }
            }

            /* Update status on every timeout (~5Hz) for live dashboard */
            const char *st = "WAITING";
            if (pipeline.state == STATE_CALIBRATION && esp1_known) st = "CALIBRATION";
            else if (pipeline.state == STATE_SEGMENTATION) st = "RECORDING";
            else if (pipeline.state == STATE_MONITORING) st = "MONITORING";
            else if (esp1_known) st = "ACTIVE";
            write_status_json(&pipeline, st);
            continue;
        }
        if (buf[0] != DEVICE_ID_THIGH_SHIN) continue;

        esp1_miss_count = 0;
        if (!esp1_known) {
            esp1_addr = from;
            esp1_known = 1;
            inet_ntop(AF_INET, &from.sin_addr, esp1_ip_str, sizeof(esp1_ip_str));
            printf("[Main] ESP#1 (thigh/shin) connected from %s\n", esp1_ip_str);
        }

        struct timespec now_ts;
        clock_gettime(CLOCK_MONOTONIC, &now_ts);
        float ts_ms = (now_ts.tv_sec * 1000.0f + now_ts.tv_nsec / 1e6f) - start_ms;

        SensorPacket pkt;
        parse_thigh_shin(buf, ts_ms, &pkt);

        pthread_mutex_lock(&foot_lock);
        pkt.foot = latest_foot;
        pthread_mutex_unlock(&foot_lock);

        if (!calibration_display_sent && esp2_known) {
            send_display(0, 0, 1);
            calibration_display_sent = 1;
        }

        /* ---- RECORD MODE ---- */
        if (run_mode == MODE_RECORD) {
            PipelineState prev_state = pipeline.state;
            pipeline_step(&pipeline, &pkt);

            if (prev_state == STATE_CALIBRATION && pipeline.state == STATE_SEGMENTATION) {
                send_display(0, 0, 2);
                printf("[Record] Calibrated. Start walking...\n");
                write_status_json(&pipeline, "RECORDING");
            }

            if (pipeline.state == STATE_SEGMENTATION) {
                /* Show stride count as it accumulates */
                static int last_printed = 0;
                if (pipeline.seg.n_valid != last_printed) {
                    printf("[Record] Stride %d collected\n", pipeline.seg.n_valid);
                    last_printed = pipeline.seg.n_valid;
                    write_status_json(&pipeline, "RECORDING");
                }
            }

            /* Update status periodically */
            status_counter++;
            if (status_counter % 50 == 0) {
                const char *st = "CALIBRATION";
                if (pipeline.state == STATE_SEGMENTATION) st = "RECORDING";
                write_status_json(&pipeline, st);
            }
        }

        /* ---- TEST MODE ---- */
        else {
            if (pipeline.state == STATE_CALIBRATION) {
                /* Run calibration phase manually */
                int i = pipeline.calib_count;
                if (i < CALIB_SAMPLES) {
                    pipeline.calib_thigh[i] = accel_to_angle(pkt.thigh.ax, pkt.thigh.az);
                    pipeline.calib_shin[i]  = accel_to_angle(pkt.shin.ax, pkt.shin.az);
                    pipeline.calib_foot[i]  = accel_to_angle(pkt.foot.ax, pkt.foot.az);
                    pipeline.calib_count++;

                    if (pipeline.calib_count >= CALIB_SAMPLES) {
                        float mt = 0, ms = 0, mf = 0;
                        for (int j = 0; j < CALIB_SAMPLES; j++) {
                            mt += pipeline.calib_thigh[j];
                            ms += pipeline.calib_shin[j];
                            mf += pipeline.calib_foot[j];
                        }
                        mt /= CALIB_SAMPLES; ms /= CALIB_SAMPLES; mf /= CALIB_SAMPLES;
                        ac_set_baseline(&pipeline.angles, mt, ms, mf);
                        pipeline.state = STATE_MONITORING;
                        printf("[Test] Calibrated. Monitoring against saved profile...\n");
                        send_display(0, 0, 2);
                        write_status_json(&pipeline, "MONITORING");
                    }
                }

                status_counter++;
                if (status_counter % 50 == 0)
                    write_status_json(&pipeline, "CALIBRATION");

            } else if (pipeline.state == STATE_MONITORING) {
                /* Compute angles and feed to segmenter */
                float knee, ankle;
                ac_update(&pipeline.angles, &pkt, &knee, &ankle);

                if (seg_feed(&pipeline.seg, &pkt, knee, ankle)) {
                    StrideBuffer *sb = &pipeline.seg.last_completed;
                    if (sb->count >= 5) {
                        float obs_k[GAIT_CYCLE_PTS], obs_a[GAIT_CYCLE_PTS];
                        interp_linear(sb->knee, sb->count, obs_k, GAIT_CYCLE_PTS);
                        interp_linear(sb->ankle, sb->count, obs_a, GAIT_CYCLE_PTS);

                        pipeline.stride_count++;
                        StrideResult result = score_stride(obs_k, obs_a,
                            &pipeline.twin, &pipeline.profile, pipeline.stride_count);

                        print_result(&result);
                        add_stride_result(&result);
                        send_haptic(result.haptic);

                        int color_code = 0;
                        if (result.ghs < 80) color_code = 1;
                        if (result.ghs < 50) color_code = 2;
                        send_display(result.ghs, color_code, 2);
                        write_status_json(&pipeline, "MONITORING");
                    }
                }
            }
        }
    }

    /* ---- Shutdown ---- */
    printf("\n[Main] Shutting down...\n");

    /* In record mode, save the profile on Ctrl+C */
    if (run_mode == MODE_RECORD && pipeline.seg.n_valid >= 5) {
        printf("[Record] Saving profile with %d strides...\n", pipeline.seg.n_valid);
        build_profile(&pipeline);
        generate_twin(&pipeline);
        save_profile(&pipeline.profile, &pipeline.twin, PROFILE_PATH);
    } else if (run_mode == MODE_RECORD) {
        printf("[Record] Not enough strides to save (need at least 5, got %d)\n",
               pipeline.seg.n_valid);
    }

    write_status_json(&pipeline, "STOPPED");

    close(sock1);
    close(sock2);
    close(cmd_sock);
    pthread_join(foot_tid, NULL);
    printf("=== Done ===\n");
    return 0;
}
