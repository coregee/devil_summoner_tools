; Rebuild atlas-native name rows after LOAD.BIN restores the five saved
; eight-byte ASCII fields.  The WRAM contract is shared with NAME.BIN.
load_namefix:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    sts.l   pr, @-r15
    mov     #0, r8
lnf_field:
    mov.l   =stage_ptrs, r1
    mov     r8, r0
    shll2   r0
    mov.l   @(r0,r1), r9
    mov     #18, r1
    mov     r8, r0
    mulu.w  r1, r0
    mov.l   =NAME_FW, r10
    sts     macl, r0
    add     r0, r10
    mov     #0, r2
    mov     #0, r11
lnf_scan:
    mov     r9, r1
    add     r2, r1
    mov.b   @r1, r1
    extu.b  r1, r0
    tst     r0, r0
    bt      lnf_sk
    cmp/eq  #0x20, r0
    bt      lnf_sk
    mov     r2, r11
    add     #1, r11
lnf_sk:
    add     #1, r2
    mov     r2, r0
    cmp/eq  #8, r0
    bf      lnf_scan
    mov     #0, r2
    tst     r11, r11
    bt      lnf_term
lnf_wr:
    mov     r9, r1
    add     r2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    shll    r0
    mov.l   =byte_to_atlas, r3
    mov.w   @(r0,r3), r1
    extu.w  r1, r1
    mov.w   r1, @r10
    add     #2, r10
    add     #1, r2
    cmp/eq  r11, r2
    bf      lnf_wr
lnf_term:
    mov.w   =0x8000, r1
    mov.w   r1, @r10
    add     #1, r8
    mov     r8, r0
    cmp/eq  #5, r0
    bf      lnf_field

    ; Rebuild the combined first/separator/last row from the authored slot
    ; name template. Empty fields retain the mature runtime behaviour here.
    mov.l   =0x00008000, r3
    mov.l   =NAME_FW, r9
    mov.l   =NAME_FW_FULL, r10
lnf_f1:
    mov.w   @r9+, r1
    extu.w  r1, r0
    cmp/eq  r3, r0
    bt      lnf_f2
    mov.w   r1, @r10
    bra     lnf_f1
    add     #2, r10
lnf_f2:
    mov.w   =name_separator_glyph, r1
    mov.w   r1, @r10
    add     #2, r10
    mov.l   =NAME_FW, r9
    add     #18, r9
lnf_f3:
    mov.w   @r9+, r1
    extu.w  r1, r0
    cmp/eq  r3, r0
    bt      lnf_f4
    mov.w   r1, @r10
    bra     lnf_f3
    add     #2, r10
lnf_f4:
    mov.w   r1, @r10
    mov.l   =prep_names, r1
    jsr     @r1
    nop

    ; The stock routine copies a Japanese FONT8 codename. Replace that copy
    ; with the generated FONT8 mapping of the saved ASCII bytes.
    mov.l   =stage_ptrs, r1
    mov.l   @(8,r1), r9
    mov.l   =CODENAME, r10
    mov     #8, r8
lnf_cn:
    mov.b   @r9+, r0
    extu.b  r0, r0
    mov.l   =byte_to_font8, r2
    mov.b   @(r0,r2), r1
    mov.b   r1, @r10
    add     #1, r10
    dt      r8
    bf      lnf_cn
    lds.l   @r15+, pr
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
