.PHONY: all check-toolchain clean
all: check-toolchain
	mkdir -p build
	$(CROSS_COMPILE)gcc -std=c99 -Wall -Wextra -Werror -O2 main.c -o build/hello_hi3516
	$(CROSS_COMPILE)readelf -h -l -A build/hello_hi3516 > build/hello_hi3516.elf.txt
	sha256sum build/hello_hi3516 > build/hello_hi3516.sha256

check-toolchain:
	@test -n "$(CROSS_COMPILE)" || { echo 'Set CROSS_COMPILE to the verified SDK compiler prefix; host gcc is not a fallback.' >&2; exit 1; }
	@command -v "$(CROSS_COMPILE)gcc" >/dev/null
	@command -v "$(CROSS_COMPILE)readelf" >/dev/null

clean:
	rm -rf build
