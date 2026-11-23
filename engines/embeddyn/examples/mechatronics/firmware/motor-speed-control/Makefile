# Builds ../motor-speed-control.elf with arm-none-eabi-gcc (no SDK needed).
# Default: interrupt + WFI pacing. `make POLL=1` builds the flag-polling variant
# (about 10x more CPU to emulate). Use `make -B` when switching variants.
CC = arm-none-eabi-gcc
CFLAGS = $(if $(POLL),,-DUSE_IRQ) -mcpu=cortex-m4 -mthumb -mfloat-abi=soft -O2 -g -Wall -Wextra -ffreestanding -ffunction-sections
LDFLAGS = -nostdlib -T link.ld -Wl,--gc-sections -Wl,-Map=build/motor-speed-control.map
OUT = ../motor-speed-control.elf

# Some distro packages (e.g. Ubuntu 24.04 binutils-arm-none-eabi) lack the
# <prefix>/arm-none-eabi/bin/{as,ld} links gcc searches; provide them via -B.
TOOLBIN = build/toolbin

$(OUT): main.c startup.c link.ld $(TOOLBIN)/as
	$(CC) -B$(TOOLBIN)/ $(CFLAGS) $(LDFLAGS) -o $@ main.c startup.c -lgcc

$(TOOLBIN)/as:
	mkdir -p $(TOOLBIN)
	ln -sf "$$(command -v arm-none-eabi-as)" $(TOOLBIN)/as
	ln -sf "$$(command -v arm-none-eabi-ld)" $(TOOLBIN)/ld

clean:
	rm -f $(OUT) build/motor-speed-control.map $(TOOLBIN)/as $(TOOLBIN)/ld
.PHONY: clean
