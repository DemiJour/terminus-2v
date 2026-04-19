package main

import (
	"fmt"
	"os"

	_ "gotpatch/internal/chaff"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintf(os.Stderr, "usage: %s <input_elf> <output_elf> [wrapper_symbol]\n", os.Args[0])
		os.Exit(2)
	}
	fmt.Fprintf(os.Stderr, "got-patch: not implemented — replace this file with a working ELF64 LE patcher.\n")
	os.Exit(1)
}
