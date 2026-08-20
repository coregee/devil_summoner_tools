; Rebuild the dynamic city/ward row in four FONT16 cells.  The input ABI is
; r4 = five-word destination row and r5 = generated FONT16 source row.
map_name_compose:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r14
    mov     r5, r13

    ; Upload the five authored fixed-label strips alongside the dynamic rows.
    mov.l   =FIXED_SRC, r1
    mov.l   =FIXED_DST, r2
    mov.w   =FIXED_LONGS, r3
mn_fixed_copy:
    mov.l   @r1+, r0
    mov.l   r0, @r2
    add     #4, r2
    dt      r3
    bf      mn_fixed_copy
    bra     mn_after_fixed_pool
    nop
    .pool
mn_after_fixed_pool:

    mov.w   =WARD_CODE, r12
    mov.l   =CITY_ROW_ADDR, r0
    cmp/eq  r0, r14
    bf      mn_code_ready
    mov.w   =CITY_CODE, r12
mn_code_ready:
    mov     r12, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r11
    add     r0, r11

    mov     #0, r0
    mov     r11, r1
    mov     #32, r2
mn_clear:
    mov.l   r0, @r1
    add     #4, r1
    dt      r2
    bf      mn_clear

    mov     r14, r3
    mov     r12, r1
    mov     #4, r2
mn_codes:
    mov.w   r1, @r3
    add     #2, r3
    add     #1, r1
    dt      r2
    bf      mn_codes
    mov.w   =TERM, r0
    mov.w   r0, @r3

    mov     #0, r12
    mov     r13, r9
    mov     #8, r10
mn_measure:
    mov.w   @r9+, r0
    mov.w   =TERM, r3
    cmp/eq  r3, r0
    bt      mn_measure_done
    ; Compare the sign-extended terminator before zero-extending the code.
    extu.w  r0, r0
    bsr     mn_width
    nop
    add     r0, r12
    dt      r10
    bf      mn_measure
mn_measure_done:
    mov     #NAME_WIDTH, r0
    cmp/hs  r12, r0
    bt      mn_unscaled

    ; Build floor(source_x * NAME_WIDTH / measured_width) once for all rows.
    mov.l   =SCALE_MAP, r1
    mov     #0, r2
    mov     #0, r3
    mov     #NAME_WIDTH, r0
    shll    r0
mn_scale_map:
    mov.b   r2, @r1
    add     #1, r1
    add     #NAME_WIDTH, r3
    cmp/hs  r12, r3
    bf      mn_scale_map_next
    sub     r12, r3
    add     #1, r2
mn_scale_map_next:
    dt      r0
    bf      mn_scale_map

    mov     #0, r8
    mov     r13, r9
    mov     #8, r10
mn_scaled_glyph:
    mov.w   @r9+, r0
    mov.w   =TERM, r3
    cmp/eq  r3, r0
    bf      mn_scaled_not_done
    bra     mn_done
    nop
mn_scaled_not_done:
    extu.w  r0, r0
    mov     r0, r14
    bsr     mn_width
    nop
    mov     r0, r7

    mov     r14, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r6
    add     r0, r6
    mov     #0, r4
    mov     #16, r14
mn_scaled_row:
    mov.w   @r6+, r0
    extu.w  r0, r5
    swap.w  r5, r5
    mov.l   =SCALE_MAP, r3
    add     r8, r3
    mov     #16, r2
mn_scaled_pixel:
    mov.b   @r3+, r0
    extu.b  r0, r0
    shll    r5
    bf      mn_scaled_pixel_next
    mov     #NAME_WIDTH, r1
    cmp/hs  r1, r0
    bt      mn_scaled_pixel_next

    mov     r0, r1
    mov     #15, r12
    and     r1, r12
    mov     #15, r13
    sub     r12, r13
    mov     #1, r12
    tst     r13, r13
    bt      mn_scaled_mask_ready
mn_scaled_mask:
    shll    r12
    dt      r13
    bf      mn_scaled_mask
mn_scaled_mask_ready:
    shlr2   r1
    shlr2   r1
    shll2   r1
    shll2   r1
    shll    r1
    add     r11, r1
    add     r4, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    or      r12, r0
    mov.w   r0, @r1
mn_scaled_pixel_next:
    dt      r2
    bf      mn_scaled_pixel
    add     #2, r4
    dt      r14
    bf      mn_scaled_row
    add     r7, r8
    dt      r10
    bf      mn_scaled_glyph
    bra     mn_done
    nop

mn_unscaled:
    mov     #0, r8
    mov     r13, r9
    mov     #8, r10
mn_glyph:
    mov.w   @r9+, r0
    mov.w   =TERM, r3
    cmp/eq  r3, r0
    bt      mn_done
    extu.w  r0, r0
    mov     r0, r14
    bsr     mn_width
    nop
    mov     r0, r7

    mov     r8, r5
    shlr2   r5
    shlr2   r5
    mov     #4, r0
    cmp/hs  r0, r5
    bt      mn_done

    mov     r14, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r6
    add     r0, r6
    mov     r5, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov     r11, r3
    add     r0, r3
    mov     #16, r4
mn_row:
    mov.w   @r6+, r0
    extu.w  r0, r0
    swap.w  r0, r0
    mov     r8, r1
    mov     #15, r2
    and     r2, r1
    tst     r1, r1
    bt      mn_shifted
mn_shift:
    shlr    r0
    dt      r1
    bf      mn_shift
mn_shifted:
    mov     r0, r14
    mov     r0, r1
    swap.w  r1, r1
    extu.w  r1, r1
    mov.w   @r3, r2
    extu.w  r2, r2
    or      r1, r2
    mov.w   r2, @r3

    mov     r5, r1
    mov     #3, r0
    cmp/eq  r0, r1
    bt      mn_next_row
    mov     r3, r2
    add     #32, r2
    mov     r14, r1
    extu.w  r1, r1
    mov.w   @r2, r0
    extu.w  r0, r0
    or      r1, r0
    mov.w   r0, @r2
mn_next_row:
    add     #2, r3
    dt      r4
    bf      mn_row
    add     r7, r8
    dt      r10
    bf      mn_glyph
    bra     mn_done
    nop

mn_width:
    mov.w   =WIDTH_LIMIT, r1
    cmp/hs  r1, r0
    bt      mn_fullwidth
    mov     r0, r2
    mova    widths, r0
    mov.b   @(r0,r2), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      mn_width_done
mn_fullwidth:
    mov     #16, r0
mn_width_done:
    rts
    nop

mn_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    nop
    .pool
    .align  4
widths:
