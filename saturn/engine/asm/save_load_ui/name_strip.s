; Compose the authored {first_name}<separator>{last_name} template into the
; eight FONT16 scratch cells used by both SAVE.BIN and LOAD.BIN.  The first
; call renders the complete strip; the remaining seven stock calls are no-ops.
name_strip:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    mov     r5, r13
    mov     r2, r5
    add     #-4, r5

    mov     r13, r0
    mov     #7, r1
    and     r1, r0
    mov     r13, r12
    mov     #-8, r1
    and     r1, r12
    mov     r12, r1
    shll2   r1
    shll2   r1
    shll    r1
    mov.l   =FONT16_BASE, r12
    add     r1, r12

    tst     r0, r0
    bt      sns_compose
    bra     sns_done
    nop

sns_compose:
    mov     #0, r1
    mov     r12, r2
    mov     #64, r3
sns_clear:
    mov.l   r1, @r2
    add     #4, r2
    dt      r3
    bf      sns_clear

    ; Compact the adjacent eight-byte fields. Null padding is discarded and
    ; the asset-owned separator is retained only when both fields are present.
    mov.l   =name_buffer, r11
    mov     r11, r9
    mov     r5, r6
    mov     #0, r8
    mov     #8, r7
sns_copy_first:
    mov.b   @r6+, r0
    tst     r0, r0
    bt      sns_first_next
    mov.b   r0, @r9
    add     #1, r9
    add     #1, r8
sns_first_next:
    dt      r7
    bf      sns_copy_first

    tst     r8, r8
    bt      sns_copy_last_start
    mov     #NAME_SEPARATOR, r0
    mov.b   r0, @r9
    add     #1, r9
sns_copy_last_start:
    mov     #0, r10
    mov     #8, r7
sns_copy_last:
    mov.b   @r6+, r0
    tst     r0, r0
    bt      sns_last_next
    mov.b   r0, @r9
    add     #1, r9
    add     #1, r10
sns_last_next:
    dt      r7
    bf      sns_copy_last

    tst     r10, r10
    bf      sns_join_ready
    tst     r8, r8
    bt      sns_join_ready
    add     #-1, r9
sns_join_ready:
    mov     #0, r0
    mov.b   r0, @r9
    sub     r11, r9
    mov     r9, r13

    mov     #0, r10
    mov     r11, r9
    mov     r13, r8
    tst     r8, r8
    bf      sns_measure
    bra     sns_done
    nop
sns_measure:
    mov.b   @r9+, r0
    extu.b  r0, r0
    mov.l   =byte_to_width, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    add     r0, r10
    dt      r8
    bf      sns_measure

    mov.w   =NAME_WIDTH, r0
    cmp/hs  r10, r0
    bt      sns_unscaled

    ; Build floor(source_x * 128 / measured_width). The extra 16 entries
    ; cover visible pixels extending beyond a glyph's proportional advance.
    mov.l   =name_scale_map, r1
    mov     #0, r2
    mov     #0, r3
    mov     r10, r0
    add     #16, r0
sns_scale_map:
    mov.b   r2, @r1
    add     #1, r1
    add     #127, r3
    add     #1, r3
    cmp/hs  r10, r3
    bf      sns_scale_map_next
    sub     r10, r3
    add     #1, r2
sns_scale_map_next:
    dt      r0
    bf      sns_scale_map

    mov     #0, r8
    mov     r11, r9
    mov     r13, r10
sns_scaled_glyph:
    mov.b   @r9+, r14
    extu.b  r14, r14
    mov     r14, r0
    mov.l   =byte_to_width, r1
    mov.b   @(r0,r1), r7
    extu.b  r7, r7

    mov     r14, r0
    shll    r0
    mov.l   =byte_to_atlas, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT16_BASE, r6
    add     r0, r6
    mov     #0, r4
    mov     #16, r14
sns_scaled_row:
    mov.w   @r6+, r0
    extu.w  r0, r5
    swap.w  r5, r5
    mov.l   =name_scale_map, r3
    add     r8, r3
    mov     #16, r2
sns_scaled_pixel:
    mov.b   @r3+, r0
    extu.b  r0, r0
    shll    r5
    bf      sns_scaled_pixel_next
    mov.w   =NAME_WIDTH, r1
    cmp/hs  r1, r0
    bt      sns_scaled_pixel_next

    mov     r0, r1
    mov     #15, r13
    and     r1, r13
    mov     #15, r0
    sub     r13, r0
    mov     #1, r13
    tst     r0, r0
    bt      sns_scaled_mask_ready
sns_scaled_mask:
    shll    r13
    dt      r0
    bf      sns_scaled_mask
sns_scaled_mask_ready:
    shlr2   r1
    shlr2   r1
    shll2   r1
    shll2   r1
    shll    r1
    add     r12, r1
    add     r4, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    or      r13, r0
    mov.w   r0, @r1
sns_scaled_pixel_next:
    dt      r2
    bf      sns_scaled_pixel
    add     #2, r4
    dt      r14
    bf      sns_scaled_row
    add     r7, r8
    dt      r10
    bf      sns_scaled_glyph
    bra     sns_done
    nop

sns_unscaled:
    mov     #0, r8
    mov     r11, r9
    mov     r13, r10
sns_glyph:
    mov.b   @r9+, r14
    extu.b  r14, r14
    mov     r14, r0
    mov.l   =byte_to_width, r1
    mov.b   @(r0,r1), r7
    extu.b  r7, r7

    mov     r8, r5
    shlr2   r5
    shlr2   r5
    mov     #8, r0
    cmp/hs  r0, r5
    bt      sns_done

    mov     r14, r0
    shll    r0
    mov.l   =byte_to_atlas, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT16_BASE, r6
    add     r0, r6
    mov     r5, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov     r12, r3
    add     r0, r3
    mov     #16, r4
sns_row:
    mov.w   @r6+, r0
    extu.w  r0, r0
    swap.w  r0, r0
    mov     r8, r1
    mov     #15, r2
    and     r2, r1
    tst     r1, r1
    bt      sns_shifted
sns_shift:
    shlr    r0
    dt      r1
    bf      sns_shift
sns_shifted:
    mov     r0, r14
    mov     r0, r1
    swap.w  r1, r1
    extu.w  r1, r1
    mov.w   @r3, r2
    extu.w  r2, r2
    or      r1, r2
    mov.w   r2, @r3

    mov     r5, r1
    mov     #7, r0
    cmp/eq  r0, r1
    bt      sns_next_row
    mov     r3, r2
    add     #32, r2
    mov     r14, r1
    extu.w  r1, r1
    mov.w   @r2, r0
    extu.w  r0, r0
    or      r1, r0
    mov.w   r0, @r2
sns_next_row:
    add     #2, r3
    dt      r4
    bf      sns_row
    add     r7, r8
    dt      r10
    bf      sns_glyph

sns_done:
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    mov     #1, r0
    .pool
