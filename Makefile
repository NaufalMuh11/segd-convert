CC = gcc
CFLAGS = -O2 -Wall -Wextra
LDLIBS = -lm

fairfield_segd2segy: fairfield_segd2segy.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f fairfield_segd2segy

.PHONY: clean
