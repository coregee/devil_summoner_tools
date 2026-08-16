; Sort the three parallel fusion-roster arrays by the English demon-name pool.
; DVL_OFFSETS is indexed by one-based demon ID and was emitted in normalized
; English order, so its u16 values are complete collation ranks. Duplicate
; display names use demon ID as a deterministic secondary key.
fusion_english_name_sort:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15

    mov.l   =ROSTER_COUNT, r0
    mov.w   @r0, r8
    extu.w  r8, r8
    mov     #2, r0
    cmp/hs  r0, r8
    bf      fusion_name_sort_done

    shll    r8
    mov.l   =ROSTER_IDS_PTR, r0
    mov.l   @r0, r10
    mov.l   =ROSTER_AUX0_PTR, r0
    mov.l   @r0, r11
    mov.l   =ROSTER_AUX1_PTR, r0
    mov.l   @r0, r12
    mov.l   =DVL_OFFSETS, r13
    mov     #0, r9

fusion_name_sort_outer:
    mov     r9, r6
    add     #2, r6

fusion_name_sort_inner:
    cmp/hs  r8, r6
    bt      fusion_name_sort_next_outer

    mov     r9, r0
    mov.w   @(r0,r10), r4
    extu.w  r4, r4
    add     #-1, r4
    shll    r4
    mov     r4, r0
    mov.w   @(r0,r13), r4
    extu.w  r4, r4

    mov     r6, r0
    mov.w   @(r0,r10), r5
    extu.w  r5, r5
    add     #-1, r5
    shll    r5
    mov     r5, r0
    mov.w   @(r0,r13), r5
    extu.w  r5, r5

    cmp/hi  r5, r4
    bt      fusion_name_sort_swap
    cmp/eq  r5, r4
    bf      fusion_name_sort_no_swap

    mov     r9, r0
    mov.w   @(r0,r10), r4
    extu.w  r4, r4
    mov     r6, r0
    mov.w   @(r0,r10), r5
    extu.w  r5, r5
    cmp/hi  r5, r4
    bf      fusion_name_sort_no_swap

fusion_name_sort_swap:
    mov     r9, r0
    mov.w   @(r0,r10), r1
    mov     r6, r0
    mov.w   @(r0,r10), r2
    mov.w   r1, @(r0,r10)
    mov     r9, r0
    mov.w   r2, @(r0,r10)

    mov     r9, r0
    mov.w   @(r0,r11), r1
    mov     r6, r0
    mov.w   @(r0,r11), r2
    mov.w   r1, @(r0,r11)
    mov     r9, r0
    mov.w   r2, @(r0,r11)

    mov     r9, r0
    mov.w   @(r0,r12), r1
    mov     r6, r0
    mov.w   @(r0,r12), r2
    mov.w   r1, @(r0,r12)
    mov     r9, r0
    mov.w   r2, @(r0,r12)

fusion_name_sort_no_swap:
    bra     fusion_name_sort_inner
    add     #2, r6

fusion_name_sort_next_outer:
    add     #2, r9
    mov     r8, r14
    add     #-2, r14
    cmp/hs  r14, r9
    bf      fusion_name_sort_outer

fusion_name_sort_done:
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
