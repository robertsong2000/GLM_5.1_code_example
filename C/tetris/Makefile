CC = gcc
CFLAGS = -Wall -Wextra -O2
TARGET = tetris

all: $(TARGET)

$(TARGET): tetris.c
	$(CC) $(CFLAGS) -o $(TARGET) tetris.c

clean:
	rm -f $(TARGET)

run: $(TARGET)
	./$(TARGET)

.PHONY: all clean run
