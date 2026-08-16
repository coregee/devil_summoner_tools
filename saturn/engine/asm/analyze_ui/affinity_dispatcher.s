affinity_dispatcher:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    sts.l   pr, @-r15
    mov     r6, r12
    mov     r7, r13
    mov.l   =SELECTOR, r0
    mov.b   @r0, r0
    extu.b  r0, r0
    add     #-32, r0
    mov     #66, r1
    cmp/hs  r1, r0
    bt      affinity_fallback
    mov.l   =AFFINITY_TOKENS, r8
    tst     r0, r0
    bt      affinity_select_line
affinity_skip_record:
    mov.b   @r8+, r1
    tst     r1, r1
    bf      affinity_skip_record
    add     #-1, r0
    tst     r0, r0
    bf      affinity_skip_record
affinity_select_line:
    mov.l   @(24,r15), r0
    tst     r0, r0
    bt      affinity_compose
affinity_find_line:
    mov.b   @r8+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      affinity_empty
    cmp/eq  #30, r0
    bf      affinity_find_line
affinity_compose:
    add     #-36, r15
    mov     r15, r9
    mov     #0, r10
affinity_token:
    mov.b   @r8+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      affinity_draw
    cmp/eq  #30, r0
    bt      affinity_draw
    cmp/eq  #29, r0
    bt      affinity_comma
    cmp/eq  #31, r0
    bt      affinity_colon
    tst     r10, r10
    bt      affinity_word
    mov     #63, r1
    mov.b   r1, @r9
    add     #1, r9
affinity_word:
    add     #-1, r0
    mov.l   =WORD_OFFSETS, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    mov.l   =WORD_POOL, r1
    add     r0, r1
affinity_copy_word:
    mov.b   @r1+, r0
    tst     r0, r0
    bt      affinity_word_done
    mov.b   r0, @r9
    add     #1, r9
    bra     affinity_copy_word
    nop
affinity_word_done:
    mov     #1, r10
    bra     affinity_token
    nop
affinity_comma:
    mov     #-27, r0
    bra     affinity_punctuation
    nop
affinity_colon:
    mov     #-42, r0
affinity_punctuation:
    mov.b   r0, @r9
    add     #1, r9
    mov     #63, r0
    mov.b   r0, @r9
    add     #1, r9
    mov     #0, r10
    bra     affinity_token
    nop
affinity_draw:
    cmp/eq  r15, r9
    bt      affinity_terminate
    mov     r9, r0
    add     #-1, r0
    mov.b   @r0, r0
    extu.b  r0, r0
    cmp/eq  #63, r0
    bf      affinity_terminate
    add     #-1, r9
affinity_terminate:
    mov     #0, r0
    mov.b   r0, @r9
    mov     r15, r4
    add     #36, r15
    mov.l   @(24,r15), r8
    mov.l   @(28,r15), r9
    mov.l   @(32,r15), r10
    add     #-36, r15
    mov     #-1, r5
    mov     r12, r6
    mov     r13, r7
    add     #4, r8
    mov.l   r10, @-r15
    mov.l   r9, @-r15
    mov.l   r8, @-r15
    mov.l   =FONT8_VWF, r0
    jsr     @r0
    nop
    add     #12, r15
    add     #36, r15
    bra     affinity_restore
    nop
affinity_empty:
    add     #-36, r15
    mov     r15, r9
    bra     affinity_draw
    mov     #0, r10
affinity_fallback:
    lds.l   @r15+, pr
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =STOCK, r0
    jmp     @r0
    nop
affinity_restore:
    lds.l   @r15+, pr
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align 4
