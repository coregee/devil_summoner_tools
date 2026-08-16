active_row_renderer:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-12, r15
    mov.l   r4, @r15
    mov.l   r5, @(4,r15)
    mov.l   r6, @(8,r15)
    mov     r7, r12
    mov.w   @r15, r14
    mov.l   @(40,r15), r10
    mov     r10, r0
    add     r10, r0
    mov.l   =SELECTION_TABLE, r1
    mov.w   @(r0,r1), r13
    mov.l   =ACTIVE_CACHE, r0
    mov.w   @r0, r1
    cmp/eq  r10, r1
    bf      update_cache
    mov     r0, r2
    add     #2, r2
    mov.w   @r2, r1
    cmp/eq  r13, r1
    bf      update_cache
    mov     #0, r10
    bra     cache_ready
    nop
update_cache:
    mov.w   r10, @r0
    add     #2, r0
    mov.w   r13, @r0
    mov     #1, r10
cache_ready:
    mov     #0, r8
row_loop:
    cmp/hs  r14, r8
    bt      row_done
    mov     r8, r1
    add     r8, r1
    add     r15, r1
    add     #2, r1
    mov.w   @r1, r9
    mov     #18, r1
    cmp/hi  r1, r9
    bt      numeric_row
    mov     r12, r6
    cmp/eq  r13, r8
    bf      color_ready
    tst     r10, r10
    bt      next_row
    mov.l   =BRIGHT_COLOR, r1
    mov.w   @r1, r6
    extu.w  r6, r6
color_ready:
    mov     r9, r0
    add     r9, r0
    mov.l   =LABEL_LENGTHS, r1
    mov.w   @(r0,r1), r5
    mov     #32, r1
    mul.l   r1, r9
    sts     macl, r4
    mov.l   =LABEL_TABLE, r1
    add     r1, r4
    mov     r9, r1
    add     #1, r1
    mov.l   =DRAW_CONTEXT, r2
    mov.l   r2, @-r15
    mov.l   r1, @-r15
    mov     #0, r1
    mov.l   r1, @-r15
    mov     #0, r7
    mov.l   =DRAW_LABEL, r1
    jsr     @r1
    nop
    add     #12, r15
    bra     next_row
    nop
numeric_row:
    mov     r9, r4
    add     #1, r4
    extu.w  r4, r4
    mov     r12, r5
    mov     r13, r6
    add     #-1, r6
    mov.l   =DRAW_CONTEXT, r7
    mov.l   =DRAW_NUMBER, r1
    jsr     @r1
    extu.w  r6, r6
next_row:
    add     #1, r8
    bra     row_loop
    extu.w  r8, r8
row_done:
    add     #12, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align  4
