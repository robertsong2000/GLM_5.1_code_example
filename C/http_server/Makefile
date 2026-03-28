CC      = gcc
CFLAGS  = -Wall -Wextra -O2
LDFLAGS = -lpthread
TARGET  = http_server
SRC     = http_server.c

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TARGET)

run: $(TARGET)
	./$(TARGET)
