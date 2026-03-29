CC = gcc
CFLAGS = -O2 -Wall -Wextra -std=c11
LDFLAGS = -lm -lpthread -lsocket

SRC = src/gaitguard.c src/main.c
HDR = src/gaitguard.h
BIN = gaitguard

all: $(BIN)

$(BIN): $(SRC) $(HDR)
	$(CC) $(CFLAGS) -o $(BIN) $(SRC) $(LDFLAGS)

clean:
	rm -f $(BIN)

.PHONY: all clean
