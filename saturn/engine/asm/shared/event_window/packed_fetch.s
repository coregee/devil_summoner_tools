; Expand two-token event-window records through the corpus-trained dictionary. The
; linked STATE block remembers a partially consumed word/expansion across VM
; calls; DICTIONARY remains asset-derived data, not executable code.

packed_fetch:
    mov.l   r0, @-r15
    mov.l   r3, @-r15
    mov.l   r7, @-r15
    mov.l   @r10, r1
    mov.l   =STATE, r0
    mov.l   @r0, r3
    cmp/eq  r3, r1
    bf      reset_state
    mov.l   @(8,r0), r3
    tst     r3, r3
    bf      emit_expansion
    mov.l   @(12,r0), r2
    tst     r2, r2
    bf      emit_pending

read_word:
    mov.w   @r1+, r2
    mov.l   r1, @r10
    mov.l   r1, @r0
    extu.w  r2, r2
    mov     r2, r7
    shlr8   r7
    mov     r7, r0
    add     #-8, r0
    mov     #120, r3
    cmp/hs  r3, r0
    bt      emit
    extu.b  r2, r3
    tst     r3, r3
    bt      first_token
    add     #-7, r3
    mov.l   =STATE, r0
    mov.l   r3, @(12,r0)
first_token:
    mov     r7, r2
    bra     expand_token
    add     #-8, r2

reset_state:
    mov.l   r1, @r0
    mov     #0, r3
    mov.l   r3, @(8,r0)
    mov.l   r3, @(12,r0)
    bra     read_word
    nop

emit_expansion:
    mov.l   @(4,r0), r1
    mov.b   @r1+, r2
    extu.b  r2, r2
    mov.l   r1, @(4,r0)
    add     #-1, r3
    mov.l   r3, @(8,r0)
    bra     base_token
    nop

emit_pending:
    add     #-1, r2
    mov     #0, r3
    mov.l   r3, @(12,r0)

expand_token:
    mov     #63, r3
    cmp/hs  r3, r2
    bf      base_token
    add     #-63, r2
    shll2   r2
    shll    r2
    mov.l   =DICTIONARY, r3
    add     r3, r2
    mov.b   @r2+, r3
    extu.b  r3, r3
    mov.b   @r2+, r7
    extu.b  r7, r7
    add     #-1, r3
    mov.l   =STATE, r0
    mov.l   r2, @(4,r0)
    mov.l   r3, @(8,r0)
    mov     r7, r2

base_token:
    tst     r2, r2
    bf      emit
    mov.w   =267, r2

emit:
    mov.w   r2, @r9
    mov.l   @r15+, r7
    mov.l   @r15+, r3
    mov.l   @r15+, r0
    tst     r2, r2
    bt      return_zero
    mov.l   =RETURN_CODE, r1
    jmp     @r1
    nop

return_zero:
    mov.l   =RETURN_ZERO, r1
    jmp     @r1
    nop
    .pool
