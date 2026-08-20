; Expand precomposed proportional 1bpp name tiles into the stock VDP surface.
; In: r3 = VDP bitmap base, r4 = global name index, r5 = first 16px cell,
;     r6 = nonzero pixel colour, r7 = number of cells (6 main, 7 test).
renderer:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15

    mov     r6, r8
    mov     r4, r0
    shll    r0
    mov.l   =OFFSETS, r1
    mov.w   @(r0, r1), r2
    extu.w  r2, r2
    mov.l   =BITMAPS, r9
    add     r2, r9

    mov     r5, r0
    shll8   r0
    shll    r0
    mov     r3, r10
    add     r0, r10
    mov     #64, r1
    shll    r1
    add     r1, r10

    mov     r7, r11
    shll2   r11
tile_loop:
    mov     #8, r12
row_loop:
    mov.b   @r9+, r13
    extu.b  r13, r13
    shll8   r13
    shll16  r13
    mov     #8, r14
pixel_loop:
    mov     #0, r0
    shll    r13
    bf      store_pixel
    mov     r8, r0
store_pixel:
    mov.w   r0, @r10
    add     #2, r10
    dt      r14
    bf      pixel_loop
    dt      r12
    bf      row_loop
    dt      r11
    bf      tile_loop

    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
