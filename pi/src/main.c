/*
 * GaitGuard — Main entry point for QNX / Raspberry Pi
 *
 * Receives UDP from both ESPs, runs the full pipeline,
 * sends haptic commands and display updates back.
 *
 * Usage:
 *   ./gaitguard [weights.bin]
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

static volatile int running = 1;

static void handle_sigint(int sig) {
    (void)sig;
    running = 0;
}

/* ------------------------------------------------------------------ */
/* ESP IP tracking (for sending commands back)                         */
/* ------------------------------------------------------------------ */
static struct sockaddr_in esp1_addr;
static struct sockaddr_in esp2_addr;
static int esp1_known = 0;
static int esp2_known = 0;
static int cmd_sock = -1;

/* ------------------------------------------------------------------ */
/* Latest foot reading (updated by foot thread)                        */
/* ------------------------------------------------------------------ */
static IMURaw latest_foot = {0, 0, 1.0f, 0, 0, 0};
static pthread_mutex_t foot_lock = PTHREAD_MUTEX_INITIALIZER;

/* ------------------------------------------------------------------ */
/* Send haptic command to ESP #1                                       */
/* ------------------------------------------------------------------ */
static void send_haptic(HapticPattern pat) {
    if (!esp1_known || pat == HAPTIC_NONE) return;
    uint8_t buf[2] = {(uint8_t)pat, 0xFF};
    struct sockaddr_in addr = esp1_addr;
    addr.sin_port = htons(PORT_HAPTIC_CMD);
    sendto(cmd_sock, buf, 2, 0, (struct sockaddr *)&addr, sizeof(addr));
}

/* ------------------------------------------------------------------ */
/* Send display update to ESP #2                                       */
/* ------------------------------------------------------------------ */
static void send_display(float score, int color, int state) {
    if (!esp2_known) return;
    uint16_t score_int = (uint16_t)(score * 10);
    uint8_t buf[6];
    buf[0] = 1;  /* CMD_SCORE_UPDATE */
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
/* Console output for stride results                                   */
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
            char ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &from.sin_addr, ip, sizeof(ip));
            printf("[Main] ESP#2 (foot) connected from %s\n", ip);
        }

        IMURaw foot;
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        float ts_ms = ts.tv_sec * 1000.0f + ts.tv_nsec / 1e6f;
        parse_foot(buf, ts_ms, &foot);

        pthread_mutex_lock(&foot_lock);
        latest_foot = foot;
        pthread_mutex_unlock(&foot_lock);
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */
int main(int argc, char **argv) {
    const char *weights_path = (argc > 1) ? argv[1] : "weights.bin";

    signal(SIGINT, handle_sigint);

    /* Init pipeline */
    Pipeline pipeline;
    pipeline_init(&pipeline);

    if (pipeline_load_lstm(&pipeline, weights_path) != 0) {
        printf("[Main] WARNING: Running without LSTM weights (will use mean curves as twin)\n");
    }

    /* Create UDP sockets */
    int sock1 = socket(AF_INET, SOCK_DGRAM, 0);
    int sock2 = socket(AF_INET, SOCK_DGRAM, 0);
    cmd_sock  = socket(AF_INET, SOCK_DGRAM, 0);

    int optval = 1;
    setsockopt(sock1, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));
    setsockopt(sock2, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));

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

    /* Set timeout on sock1 so we can check running flag */
    struct timeval tv = {0, 200000}; /* 200ms */
    setsockopt(sock1, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock2, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    /* Start foot receiver thread */
    pthread_t foot_tid;
    pthread_create(&foot_tid, NULL, foot_thread, &sock2);

    printf("\n=== GaitGuard Pipeline (C) ===\n");
    printf("Listening on UDP :%d (thigh/shin) and :%d (foot)\n",
           PORT_IMU_THIGH_SHIN, PORT_IMU_FOOT);
    printf("Waiting for sensor data...\n\n");

    int calibration_display_sent = 0;
    struct timespec start_ts;
    clock_gettime(CLOCK_MONOTONIC, &start_ts);
    float start_ms = start_ts.tv_sec * 1000.0f + start_ts.tv_nsec / 1e6f;

    /* Main loop: driven by thigh/shin packets at 50 Hz */
    while (running) {
        uint8_t buf[64];
        struct sockaddr_in from;
        socklen_t fromlen = sizeof(from);

        ssize_t n = recvfrom(sock1, buf, sizeof(buf), 0,
                             (struct sockaddr *)&from, &fromlen);
        if (n < 27) continue;
        if (buf[0] != DEVICE_ID_THIGH_SHIN) continue;

        if (!esp1_known) {
            esp1_addr = from;
            esp1_known = 1;
            char ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &from.sin_addr, ip, sizeof(ip));
            printf("[Main] ESP#1 (thigh/shin) connected from %s\n", ip);
        }

        /* Build packet */
        struct timespec now_ts;
        clock_gettime(CLOCK_MONOTONIC, &now_ts);
        float ts_ms = (now_ts.tv_sec * 1000.0f + now_ts.tv_nsec / 1e6f) - start_ms;

        SensorPacket pkt;
        parse_thigh_shin(buf, ts_ms, &pkt);

        pthread_mutex_lock(&foot_lock);
        pkt.foot = latest_foot;
        pthread_mutex_unlock(&foot_lock);

        /* Send calibration display on first packet */
        if (!calibration_display_sent && esp2_known) {
            send_display(0, 0, 1); /* STATE_CALIBRATING */
            calibration_display_sent = 1;
        }

        /* Pipeline step */
        PipelineState prev_state = pipeline.state;
        StrideResult *result = pipeline_step(&pipeline, &pkt);

        /* Detect state transitions */
        if (prev_state == STATE_CALIBRATION && pipeline.state == STATE_SEGMENTATION) {
            send_display(0, 0, 2); /* STATE_WALKING */
            printf("[Main] Calibration complete → Segmentation\n");
        }

        if (result) {
            print_result(result);
            send_haptic(result->haptic);

            int color_code = 0;
            if (result->ghs < 80) color_code = 1;
            if (result->ghs < 50) color_code = 2;
            send_display(result->ghs, color_code, 2);
        }
    }

    printf("\n[Main] Shutting down...\n");
    close(sock1);
    close(sock2);
    close(cmd_sock);
    pthread_join(foot_tid, NULL);
    printf("=== Done ===\n");
    return 0;
}
