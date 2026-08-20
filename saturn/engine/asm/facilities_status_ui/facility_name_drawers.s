; Shared bar/shop FONT8 VWF consumers.  The drink and Talk-role entry points
; replace complete fixed-cell row functions.  Status and party entry points
; replace stock per-glyph callbacks, draw the full translated name on the first
; cell, and suppress the remaining Japanese cells.

bar_drink_name_drawer:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     r6, r8
    mov     r4, r9
    extu.w  r5, r0
    shll    r0
    mov.l   =DRINK_OFFSETS, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =DRINK_POOL, r4
    add     r0, r4
    mov.l   =SURFACE_PTR, r0
    mov.l   @r0, r5
    mov     #20, r0
    mulu.w  r0, r9
    sts     macl, r7
    add     #4, r7
    mov     #0, r6
    mov     #32, r2
    mov     #64, r3
    bsr     bar_font8_vwf
    mov     r8, r0
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

bar_talk_role_drawer:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r6, r9
    extu.w  r5, r0
    shll    r0
    mov.l   =TALK_OFFSETS, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =TALK_POOL, r4
    add     r0, r4
    mov.l   =SURFACE_PTR, r0
    mov.l   @r0, r5
    mov     #12, r0
    mulu.w  r0, r8
    sts     macl, r7
    add     #4, r7
    mov     #0, r6
    mov     #32, r2
    mov     #64, r3
    bsr     bar_font8_vwf
    mov     r9, r0
bar_talk_role_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

; Complete replacement for EVENT.BIN FUN_06036860.  r4 is the panel stride and
; r5 is the stock highlight color.  All three callers pass the traced 176-pixel
; stride; bind it explicitly so this wrapper shares the name rows' surface ABI.
healing_all_drawer:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov     r5, r8
    mov.l   =HEALING_ALL, r4
    mov.l   =HEALING_SURFACE_PTR, r0
    mov.l   @r0, r5
    mov     #16, r6
    mov     #4, r7
    mov     #32, r2
    mov.w   =HEALING_SURFACE_WIDTH, r3
    bsr     bar_font8_vwf
    mov     r8, r0
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8

; Whole-row replacement for EVENT.BIN FUN_06036fb8.
; r4 = stride, r5/r6 = x/y, r7 = encoded party record id, stack = color.
; IDs through 0x1000 are one-based DVL records; larger IDs use their low byte
; as a character-record index.  The source globals are dereferenced exactly as
; in the stock function before the shared English name resolver is called.
healing_name_drawer:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    sts.l   pr, @-r15
    mov     r5, r9
    mov     r6, r10
    extu.w  r7, r11
    mov.l   @(24,r15), r12
    tst     r11, r11
    bt      healing_name_done
    mov     #-1, r0
    extu.w  r0, r0
    cmp/eq  r0, r11
    bt      healing_name_done
    mov.w   =4096, r1
    cmp/hi  r1, r11
    bt      healing_name_character
    mov     r11, r0
    add     #-1, r0
    shll2   r0
    shll    r0
    mov.l   =HEALING_DVL_SOURCE_PTR, r1
    bra     healing_name_source
    nop
healing_name_character:
    extu.b  r11, r0
    shll2   r0
    shll    r0
    mov.l   =HEALING_CHAR_SOURCE_PTR, r1
healing_name_source:
    mov.l   @r1, r4
    add     r0, r4
    bsr     bar_resolve_name
    nop
    tst     r0, r0
    bt      healing_name_done
    mov     r0, r4
    mov     r1, r2
    mov.l   =HEALING_SURFACE_PTR, r0
    mov.l   @r0, r5
    mov     r9, r6
    mov     r10, r7
    mov.w   =HEALING_SURFACE_WIDTH, r3
    bsr     bar_font8_vwf
    mov     r12, r0
healing_name_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align 4

bar_status_name_glyph:
    tst     r6, r6
    bt      bar_name_glyph
    rts
    nop

bar_party_name_glyph:
    mov     #8, r0
    cmp/eq  r0, r6
    bt      bar_name_glyph
    rts
    nop

bar_name_glyph:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
    mov.l   @(32,r15), r12
    mov.l   @(20,r15), r4
    add     #-1, r4
    bsr     bar_resolve_name
    nop
    tst     r0, r0
    bt      bar_name_glyph_done
    mov     r1, r13
    mov     r0, r4
    mov     r8, r5
    mov     r10, r6
    mov     r11, r7
    mov     r13, r2
    mov     r9, r3
    mov     r12, r0
    bsr     bar_font8_vwf
    nop
bar_name_glyph_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

; Resolve direct DVLNAME/CHARNAME records and the runtime party table by index.
; Other copied records use the content hash, while the dynamic player codename
; retains its live source.
bar_resolve_name:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r4, r0
    mov.l   =PARTY_SOURCE_PTR, r1
    mov.l   @r1, r1
    cmp/hs  r1, r0
    bf      bar_resolve_direct
    mov     r1, r3
    add     #48, r1
    cmp/hs  r1, r0
    bt      bar_resolve_direct
    sub     r3, r0
    tst     r0, r0
    bt      bar_resolve_codename
    mov.l   =CHAR_OFFSETS, r1
    bra     bar_resolve_index
    nop
bar_resolve_direct:
    mov.l   =CHAR_SOURCE, r1
    cmp/eq  r1, r0
    bt      bar_resolve_codename
    mov.l   =DVL_SOURCE, r1
    cmp/hs  r1, r0
    bf      bar_resolve_character
    mov.l   =DVL_SOURCE_END, r2
    cmp/hs  r2, r0
    bf      bar_resolve_dvl
bar_resolve_character:
    mov     r4, r0
    mov.l   =CHAR_SOURCE, r1
    cmp/hs  r1, r0
    bf      bar_resolve_hash
    mov.l   =CHAR_SOURCE_END, r2
    cmp/hs  r2, r0
    bt      bar_resolve_hash
    sub     r1, r0
    mov.l   =CHAR_OFFSETS, r1
    bra     bar_resolve_index
    nop
bar_resolve_dvl:
    sub     r1, r0
    mov.l   =DVL_OFFSETS, r1
bar_resolve_index:
    mov     r0, r3
    mov     #7, r2
    and     r2, r3
    tst     r3, r3
    bf      bar_resolve_hash
    shlr2   r0
bar_resolve_offset:
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =NAME_POOL, r1
    add     r1, r0
    mov     #32, r1
    bra     bar_resolve_done
    nop
bar_resolve_hash:
    bsr     bar_name_lookup
    nop
    tst     r0, r0
    bt      bar_resolve_source
    bra     bar_resolve_done
    mov     #32, r1
bar_resolve_codename:
    mov.l   =PLAYER_CODENAME, r0
    bra     bar_resolve_done
    mov     #8, r1
bar_resolve_source:
    mov     r8, r0
    mov     #8, r1
bar_resolve_done:
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8

; r4 = eight-byte source record, r0 = translated FONT8 pointer or zero.
bar_name_lookup:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   @r4, r8
    mov.l   @(4,r4), r0
    xor     r0, r8
    mov.l   =NAME_LOOKUP, r9
    mov.w   =NAME_COUNT, r2
bar_name_lookup_loop:
    mov.l   @r9, r0
    cmp/eq  r0, r8
    bt      bar_name_lookup_found
    add     #8, r9
    dt      r2
    bf      bar_name_lookup_loop
    mov     #0, r0
    bra     bar_name_lookup_done
    nop
bar_name_lookup_found:
    mov.l   @(4,r9), r0
bar_name_lookup_done:
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

; r4 = null-terminated FONT8 string, r5 = surface, r6/r7 = x/y,
; r2 = maximum glyph count, r3 = surface width, r0 = color.  The generated
; table stores ink
; widths; the established FONT8 VWF contract adds one blank pixel between
; adjacent glyphs.
bar_font8_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
    mov     r0, r12
    mov     r2, r14
    add     #-4, r15
    mov.l   r3, @r15
bar_font8_loop:
    tst     r14, r14
    bt      bar_font8_done
    mov.b   @r8+, r13
    extu.b  r13, r13
    tst     r13, r13
    bt      bar_font8_done
    mov.l   =WIDTHS, r0
    mov.b   @(r0,r13), r1
    extu.b  r1, r1
    tst     r1, r1
    bt      bar_font8_done
    mov     r9, r4
    mov.l   @r15, r5
    mov     r10, r6
    mov     r11, r7
    add     #1, r1
    add     r1, r10
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    dt      r14
    bf      bar_font8_loop
    nop
bar_font8_done:
    add     #4, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align 4

