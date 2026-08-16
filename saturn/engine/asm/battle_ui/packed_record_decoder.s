; Expand one dictionary-packed u16 record into the bounded raw-u16 scratch
; buffer. A record can produce at most 127 words plus its terminator.

decode_record:
    mov.l   r7, @-r15
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov     r5, r12
    mov     #127, r7

record_word:
    mov.w   @r4+, r6
    extu.w  r6, r6
    mov     r6, r0
    shlr8   r0
    add     #-8, r0
    mov     #120, r1
    cmp/hs  r1, r0
    bt      copy_raw_word

    mov     r6, r8
    mov     r8, r9
    extu.b  r9, r9
    tst     r9, r9
    bt      no_second_token
no_second_token:
    shlr8   r8
    add     #-8, r8

decode_token:
    mov     #63, r0
    cmp/hs  r0, r8
    bf      store_single
    add     #-63, r8
    shll2   r8
    shll    r8
    mov.l   =DICTIONARY, r10
    add     r8, r10
    mov.b   @r10+, r11
    extu.b  r11, r11

store_expansion:
    mov.b   @r10+, r0
    extu.b  r0, r0
    tst     r0, r0
    bf      expansion_ready
    mov.w   =SPACE_CODE, r0
expansion_ready:
    tst     r7, r7
    bt      store_terminator
    mov.w   r0, @r5
    add     #2, r5
    dt      r7
    dt      r11
    bf      store_expansion
    bra     token_done
    nop

store_single:
    mov     r8, r0
    tst     r0, r0
    bf      single_ready
    mov.w   =SPACE_CODE, r0
single_ready:
    tst     r7, r7
    bt      store_terminator
    mov.w   r0, @r5
    add     #2, r5
    dt      r7

token_done:
    tst     r9, r9
    bt      record_word
    mov     r9, r8
    mov     #0, r9
    add     #-8, r8
    bra     decode_token
    nop

copy_raw_word:
    mov.l   =TERMINATOR, r0
    cmp/eq  r0, r6
    bt      store_terminator
    tst     r7, r7
    bt      store_terminator
    mov.w   r6, @r5
    add     #2, r5
    dt      r7
    bra     record_word
    nop

store_terminator:
    mov.l   =TERMINATOR, r0
    mov.w   r0, @r5
    mov     r12, r0
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   @r15+, r7
    rts
    nop
