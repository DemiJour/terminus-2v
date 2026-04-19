package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"strings"
)

const (
	elfMag0 = 0x7f
	elfMag1 = 'E'
	elfMag2 = 'L'
	elfMag3 = 'F'

	elfClass64 = 2
	elfData2LSB = 1

	shtStrtab = 3
	shtRela    = 4
	shtRel     = 9
	shtDynsym  = 11
	shtSymtab  = 2

	rX8664GlobDat   = 6
	rX8664JumpSlot  = 7
	ptLoad          = 1
	symSize64       = 24
	relaEntSize64   = 24
	elf64EhdrSize   = 64
	elf64ShdrSize64 = 64
	elf64PhdrSize64 = 56
)

type elfHeader struct {
	eType      uint16
	eMachine   uint16
	eEntry     uint64
	ePhoff     uint64
	eShoff     uint64
	eEhsize    uint16
	ePhentsize uint16
	ePhnum     uint16
	eShentsize uint16
	eShnum     uint16
	eShstrndx  uint16
}

type secHeader struct {
	shName      uint32
	shType      uint32
	shFlags     uint64
	shAddr      uint64
	shOffset    uint64
	shSize      uint64
	shLink      uint32
	shInfo      uint32
	shAddralign uint64
	shEntsize   uint64
	name        string
}

type symbol struct {
	stName  uint32
	stInfo  uint8
	stOther uint8
	stShndx uint16
	stValue uint64
	stSize  uint64
	name    string
}

type relocation struct {
	rOffset   uint64
	rInfo     uint64
	rAddend   int64
	symIndex  uint32
	relocType uint32
}

type patcher struct {
	data     []byte
	hdr      elfHeader
	sections []secHeader
	dynsym   []symbol
	symbols  []symbol // symtab + dynsym (search order)
	relocs   []relocation
}

func readELFHeader(b []byte) (elfHeader, error) {
	var h elfHeader
	if len(b) < elf64EhdrSize {
		return h, fmt.Errorf("truncated ELF header")
	}
	if b[0] != elfMag0 || b[1] != elfMag1 || b[2] != elfMag2 || b[3] != elfMag3 {
		return h, fmt.Errorf("not an ELF file")
	}
	if b[4] != elfClass64 {
		return h, fmt.Errorf("only ELFCLASS64 is supported")
	}
	if b[5] != elfData2LSB {
		return h, fmt.Errorf("only little-endian ELF is supported")
	}
	h.eType = binary.LittleEndian.Uint16(b[16:])
	h.eMachine = binary.LittleEndian.Uint16(b[18:])
	h.eEntry = binary.LittleEndian.Uint64(b[24:])
	h.ePhoff = binary.LittleEndian.Uint64(b[32:])
	h.eShoff = binary.LittleEndian.Uint64(b[40:])
	h.eEhsize = binary.LittleEndian.Uint16(b[52:])
	h.ePhentsize = binary.LittleEndian.Uint16(b[54:])
	h.ePhnum = binary.LittleEndian.Uint16(b[56:])
	h.eShentsize = binary.LittleEndian.Uint16(b[58:])
	h.eShnum = binary.LittleEndian.Uint16(b[60:])
	h.eShstrndx = binary.LittleEndian.Uint16(b[62:])
	return h, nil
}

func (p *patcher) readSections() error {
	off := p.hdr.eShoff
	ent := p.hdr.eShentsize
	if ent == 0 {
		ent = elf64ShdrSize64
	}
	p.sections = make([]secHeader, 0, int(p.hdr.eShnum))
	for i := 0; i < int(p.hdr.eShnum); i++ {
		if int(off)+int(ent) > len(p.data) {
			return fmt.Errorf("section header %d out of range", i)
		}
		s := p.data[off : off+uint64(ent)]
		sh := secHeader{
			shName:      binary.LittleEndian.Uint32(s[0:4]),
			shType:      binary.LittleEndian.Uint32(s[4:8]),
			shFlags:     binary.LittleEndian.Uint64(s[8:16]),
			shAddr:      binary.LittleEndian.Uint64(s[16:24]),
			shOffset:    binary.LittleEndian.Uint64(s[24:32]),
			shSize:      binary.LittleEndian.Uint64(s[32:40]),
			shLink:      binary.LittleEndian.Uint32(s[40:44]),
			shInfo:      binary.LittleEndian.Uint32(s[44:48]),
			shAddralign: binary.LittleEndian.Uint64(s[48:56]),
			shEntsize:   binary.LittleEndian.Uint64(s[56:64]),
		}
		p.sections = append(p.sections, sh)
		off += uint64(ent)
	}
	shstr := p.sectionBytes(int(p.hdr.eShstrndx))
	for i := range p.sections {
		p.sections[i].name = cString(shstr, p.sections[i].shName)
	}
	return nil
}

func (p *patcher) sectionBytes(idx int) []byte {
	if idx < 0 || idx >= len(p.sections) {
		return nil
	}
	s := p.sections[idx]
	start := int(s.shOffset)
	end := start + int(s.shSize)
	if start < 0 || end > len(p.data) {
		return nil
	}
	return p.data[start:end]
}

func cString(tab []byte, off uint32) string {
	if int(off) >= len(tab) {
		return ""
	}
	rest := tab[off:]
	i := bytes.IndexByte(rest, 0)
	if i < 0 {
		return string(rest)
	}
	return string(rest[:i])
}

func (p *patcher) loadStringTable(idx int) []byte {
	return p.sectionBytes(idx)
}

func (p *patcher) parseSymbols() error {
	p.dynsym = nil
	p.symbols = nil
	for _, sec := range p.sections {
		switch sec.shType {
		case shtSymtab, shtDynsym:
			strTab := p.loadStringTable(int(sec.shLink))
			if strTab == nil {
				continue
			}
			num := int(sec.shSize) / symSize64
			off := int(sec.shOffset)
			for i := 0; i < num; i++ {
				o := off + i*symSize64
				if o+symSize64 > len(p.data) {
					break
				}
				b := p.data[o : o+symSize64]
				sym := symbol{
					stName:  binary.LittleEndian.Uint32(b[0:4]),
					stInfo:  b[4],
					stOther: b[5],
					stShndx: binary.LittleEndian.Uint16(b[6:8]),
					stValue: binary.LittleEndian.Uint64(b[8:16]),
					stSize:  binary.LittleEndian.Uint64(b[16:24]),
					name:    cString(strTab, binary.LittleEndian.Uint32(b[0:4])),
				}
				p.symbols = append(p.symbols, sym)
			}
		default:
		}
	}
	p.rebuildDynsymFromDotSections()
	return nil
}

// rebuildDynsymFromDotSections reparses .dynsym using the .dynstr section by name.
// Some linkers set sh_link on SHT_DYNSYM in ways that do not match our first-pass
// string table lookup; using named sections fixes empty dynamic symbol names.
func (p *patcher) rebuildDynsymFromDotSections() {
	p.dynsym = nil
	dsi, dti := -1, -1
	for i, s := range p.sections {
		switch s.name {
		case ".dynsym":
			dsi = i
		case ".dynstr":
			dti = i
		}
	}
	if dsi < 0 || dti < 0 {
		return
	}
	dynstr := p.sectionBytes(dti)
	if dynstr == nil {
		return
	}
	sec := p.sections[dsi]
	num := int(sec.shSize) / symSize64
	off := int(sec.shOffset)
	for i := 0; i < num; i++ {
		o := off + i*symSize64
		if o+symSize64 > len(p.data) {
			break
		}
		b := p.data[o : o+symSize64]
		stName := binary.LittleEndian.Uint32(b[0:4])
		p.dynsym = append(p.dynsym, symbol{
			stName:  stName,
			stInfo:  b[4],
			stOther: b[5],
			stShndx: binary.LittleEndian.Uint16(b[6:8]),
			stValue: binary.LittleEndian.Uint64(b[8:16]),
			stSize:  binary.LittleEndian.Uint64(b[16:24]),
			name:    cString(dynstr, stName),
		})
	}
}

func (p *patcher) parseRelocations() error {
	p.relocs = nil
	for _, sec := range p.sections {
		var entSize int
		switch sec.shType {
		case shtRela:
			entSize = relaEntSize64
		case shtRel:
			entSize = 16
		default:
			continue
		}
		n := int(sec.shSize) / entSize
		off := int(sec.shOffset)
		for i := 0; i < n; i++ {
			o := off + i*entSize
			if sec.shType == shtRela {
				if o+relaEntSize64 > len(p.data) {
					break
				}
				b := p.data[o : o+relaEntSize64]
				rOff := binary.LittleEndian.Uint64(b[0:8])
				rInfo := binary.LittleEndian.Uint64(b[8:16])
				rAdd := int64(binary.LittleEndian.Uint64(b[16:24]))
				symIdx := uint32(rInfo >> 32)
				rType := uint32(rInfo & 0xffffffff)
				p.relocs = append(p.relocs, relocation{
					rOffset:   rOff,
					rInfo:     rInfo,
					rAddend:   rAdd,
					symIndex:  symIdx,
					relocType: rType,
				})
			} else {
				if o+16 > len(p.data) {
					break
				}
				b := p.data[o : o+16]
				rOff := binary.LittleEndian.Uint64(b[0:8])
				rInfo := binary.LittleEndian.Uint64(b[8:16])
				symIdx := uint32(rInfo >> 32)
				rType := uint32(rInfo & 0xffffffff)
				p.relocs = append(p.relocs, relocation{
					rOffset:   rOff,
					rInfo:     rInfo,
					rAddend:   0,
					symIndex:  symIdx,
					relocType: rType,
				})
			}
		}
	}
	return nil
}

func (p *patcher) findSymbol(name string) *symbol {
	for i := range p.symbols {
		if p.symbols[i].name == name {
			return &p.symbols[i]
		}
	}
	return nil
}

func (p *patcher) findElfNamed(name string) *symbol {
	for i := range p.symbols {
		if elfUnversioned(p.symbols[i].name) == name {
			return &p.symbols[i]
		}
	}
	return nil
}

// elfUnversioned strips GNU "foo@@GLIBC_2.2.5" / "foo@VER" suffixes for name comparisons.
func elfUnversioned(n string) string {
	if i := strings.IndexByte(n, '@'); i >= 0 {
		return n[:i]
	}
	return n
}

// dynsymIndexForName finds a .dynsym slot usable in r_info for this logical name.
func (p *patcher) dynsymIndexForName(name string) int {
	best := -1
	for i := range p.dynsym {
		s := p.dynsym[i].name
		if s == name {
			return i
		}
		if elfUnversioned(s) == name {
			best = i
		}
	}
	if best >= 0 {
		return best
	}
	// Last resort: match a merged .symtab definition by {value,size} (defined symbols only).
	var ref *symbol
	for j := range p.symbols {
		if elfUnversioned(p.symbols[j].name) == name {
			ref = &p.symbols[j]
			break
		}
	}
	if ref != nil && ref.stValue != 0 {
		for i := range p.dynsym {
			if p.dynsym[i].stValue == ref.stValue && p.dynsym[i].stSize == ref.stSize {
				return i
			}
		}
	}
	return -1
}

// fileOffsetForVMA maps a runtime virtual address (r_offset in RELA) to an on-disk file offset.
func (p *patcher) fileOffsetForVMA(addr uint64) (int64, bool) {
	for _, s := range p.sections {
		if s.shSize == 0 {
			continue
		}
		if addr >= s.shAddr && addr < s.shAddr+s.shSize {
			delta := addr - s.shAddr
			if delta >= s.shSize {
				return 0, false
			}
			return int64(s.shOffset) + int64(delta), true
		}
	}
	// Fallback: map through PT_LOAD (covers GOT when section boundaries are odd).
	ent := uint64(p.hdr.ePhentsize)
	if ent == 0 {
		ent = elf64PhdrSize64
	}
	off := p.hdr.ePhoff
	for i := 0; i < int(p.hdr.ePhnum); i++ {
		o := int(off + uint64(i)*ent)
		if o+56 > len(p.data) {
			break
		}
		pt := binary.LittleEndian.Uint32(p.data[o : o+4])
		if pt != ptLoad {
			continue
		}
		pOff := binary.LittleEndian.Uint64(p.data[o+8 : o+16])
		pVaddr := binary.LittleEndian.Uint64(p.data[o+16 : o+24])
		pFilesz := binary.LittleEndian.Uint64(p.data[o+32 : o+40])
		if addr >= pVaddr && addr < pVaddr+pFilesz {
			return int64(pOff + (addr - pVaddr)), true
		}
	}
	return 0, false
}

func (p *patcher) relocationsForMalloc() []relocation {
	var out []relocation
	for _, r := range p.relocs {
		if int(r.symIndex) >= len(p.dynsym) {
			continue
		}
		sym := p.dynsym[r.symIndex]
		if elfUnversioned(sym.name) != "malloc" {
			continue
		}
		if r.relocType != rX8664GlobDat && r.relocType != rX8664JumpSlot {
			continue
		}
		out = append(out, r)
	}
	return out
}

func (p *patcher) patchRelocSymbol(from string, to string) (int, error) {
	targets := p.relocationsForMalloc()
	if len(targets) == 0 {
		return 0, fmt.Errorf("no relocations targeting symbol %q (R_X86_64_JUMP_SLOT / R_X86_64_GLOB_DAT)", from)
	}
	newIdx := p.dynsymIndexForName(to)
	if newIdx >= 0 {
		patched := 0
		for _, tr := range targets {
			for si, sec := range p.sections {
				if sec.shType != shtRela && sec.shType != shtRel {
					continue
				}
				ent := relaEntSize64
				if sec.shType == shtRel {
					ent = 16
				}
				n := int(sec.shSize) / ent
				off := int(sec.shOffset)
				for i := 0; i < n; i++ {
					o := off + i*ent
					if o+8 > len(p.data) {
						break
					}
					stored := binary.LittleEndian.Uint64(p.data[o : o+8])
					if stored != tr.rOffset {
						continue
					}
					newInfo := (uint64(uint32(newIdx)) << 32) | uint64(tr.relocType)
					binary.LittleEndian.PutUint64(p.data[o+8:o+16], newInfo)
					fmt.Fprintf(os.Stderr, "patched reloc in section %s (#%d) file_off=%d r_offset=0x%x type=%d sym->%s\n",
						p.sections[si].name, si, o, tr.rOffset, tr.relocType, to)
					patched++
				}
			}
		}
		if patched == 0 {
			return 0, fmt.Errorf("failed to locate relocation bytes on disk for %q", from)
		}
		return patched, nil
	}

	// Fallback: wrapper exists in .symtab with a VMA but not in .dynsym (linker did not export it).
	// Write the wrapper entry point directly into each targeted GOT slot (r_offset is the slot VMA).
	ref := p.findElfNamed(to)
	if ref == nil || ref.stValue == 0 {
		return 0, fmt.Errorf("wrapper symbol %q not found in .dynsym and no VMA for direct GOT patch", to)
	}
	targetVMA := ref.stValue
	patched := 0
	for _, tr := range targets {
		fo, ok := p.fileOffsetForVMA(tr.rOffset)
		if !ok {
			continue
		}
		o := int(fo)
		if o < 0 || o+8 > len(p.data) {
			continue
		}
		binary.LittleEndian.PutUint64(p.data[o:o+8], targetVMA)
		fmt.Fprintf(os.Stderr, "patched GOT slot file_off=%d vma=0x%x type=%d <- %s vma=0x%x (direct)\n",
			o, tr.rOffset, tr.relocType, to, targetVMA)
		patched++
	}
	if patched == 0 {
		return 0, fmt.Errorf("wrapper symbol %q not in .dynsym and could not map GOT VMA to file (r_offset=0x%x)", to, targets[0].rOffset)
	}
	return patched, nil
}

func (p *patcher) printSummary() {
	fmt.Fprintf(os.Stderr, "ELF64 LE image: sections=%d dynsym=%d relocations=%d\n",
		len(p.sections), len(p.dynsym), len(p.relocs))
	for _, s := range p.symbols {
		b := elfUnversioned(s.name)
		if b == "malloc" || b == "logged_malloc" || b == "free" {
			fmt.Fprintf(os.Stderr, "symbol: name=%s st_value=0x%x st_size=%d\n", s.name, s.stValue, s.stSize)
		}
	}
	for _, r := range p.relocs {
		if int(r.symIndex) >= len(p.dynsym) {
			continue
		}
		n := p.dynsym[r.symIndex].name
		if elfUnversioned(n) == "malloc" {
			fmt.Fprintf(os.Stderr, "reloc: sym=%s type=%d r_offset=0x%x r_addend=%d\n", n, r.relocType, r.rOffset, r.rAddend)
		}
	}
}

func run(inputPath, outputPath, wrapper string) error {
	raw, err := os.ReadFile(inputPath)
	if err != nil {
		return err
	}
	p := &patcher{data: append([]byte(nil), raw...)}
	var e error
	p.hdr, e = readELFHeader(p.data)
	if e != nil {
		return e
	}
	if e = p.readSections(); e != nil {
		return e
	}
	if e = p.parseSymbols(); e != nil {
		return e
	}
	if e = p.parseRelocations(); e != nil {
		return e
	}
	p.printSummary()
	if p.findElfNamed("malloc") == nil {
		return fmt.Errorf("malloc symbol not found")
	}
	n, err := p.patchRelocSymbol("malloc", wrapper)
	if err != nil {
		return err
	}
	fmt.Fprintf(os.Stderr, "patched %d relocation slot(s) for malloc -> %s\n", n, wrapper)
	if len(p.data) < elf64EhdrSize {
		return fmt.Errorf("internal: truncated image")
	}
	if len(raw) < elf64EhdrSize {
		return fmt.Errorf("internal: truncated original")
	}
	copy(p.data[:elf64EhdrSize], raw[:elf64EhdrSize])
	if err := os.WriteFile(outputPath, p.data, 0o755); err != nil {
		return err
	}
	fmt.Fprintf(os.Stderr, "wrote patched ELF to %s with file mode %#o\n", outputPath, 0o755)
	fmt.Fprintf(os.Stderr,
		"relocation filter: R_X86_64_GLOB_DAT=%d R_X86_64_JUMP_SLOT=%d (malloc targets only)\n",
		rX8664GlobDat, rX8664JumpSlot)
	return nil
}

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintf(os.Stderr, "usage: %s <input_elf> <output_elf> [wrapper_symbol]\n", os.Args[0])
		os.Exit(2)
	}
	inp := os.Args[1]
	out := os.Args[2]
	wrap := "logged_malloc"
	if len(os.Args) >= 4 {
		wrap = os.Args[3]
	}
	if err := run(inp, out, wrap); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}
