; Shared packed dispatcher for Conversation and its physical COMBAT readers.
packed_dispatch:
    mov     r4, r0
    shlr8   r0
    add     #-8, r0
    mov     #120, r1
    cmp/hs  r1, r0
    bt      raw_dispatch

    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15

    mov     r4, r8
    mov     r8, r12
    extu.b  r12, r12
    tst     r12, r12
    bt      no_second_token
no_second_token:
    mov.l   =DIALOGUE_MODE, r1
    mov.b   @r1, r13
    extu.b  r13, r13
    tst     r13, r13
    bt      output_mode_ready
    mov.l   =PENDING_BUFFER, r13
output_mode_ready:
    shlr8   r8
    add     #-8, r8
    mov.l   =RAW_HANDLER, r14
    mov     r8, r11

decode_token:
    mov     #63, r0
    cmp/hs  r0, r11
    bf      emit_single
    add     #-63, r11
    shll2   r11
    shll    r11
    mov.l   =DICTIONARY, r9
    add     r11, r9
    mov.b   @r9+, r10
    extu.b  r10, r10

expansion_loop:
    mov.b   @r9+, r4
    extu.b  r4, r4
    tst     r4, r4
    bf      emit_expansion_glyph
    mov.w   =SPACE_CODE, r4
emit_expansion_glyph:
    bsr     emit_glyph
    nop
    dt      r10
    bf      expansion_loop
    bra     token_done
    nop

emit_single:
    mov     r11, r4
    tst     r4, r4
    bf      emit_single_glyph
    mov.w   =SPACE_CODE, r4
emit_single_glyph:
    bsr     emit_glyph
    nop

token_done:
    tst     r12, r12
    bt      packed_done
    mov     r12, r11
    mov     #0, r12
    add     #-8, r11
    bra     decode_token
    nop

packed_done:
    tst     r13, r13
    bt      restore_dispatch
    mov.w   =TERMINATOR, r0
    mov.w   r0, @r13
    mov.l   =PENDING_FLAG, r1
    mov     #1, r0
    mov.w   r0, @r1
    mov.l   =PENDING_BUFFER, r1
    mov.w   @r1, r4
    extu.w  r4, r4
    jsr     @r14
    nop

restore_dispatch:
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

emit_glyph:
    tst     r13, r13
    bt      emit_glyph_now
    mov.w   r4, @r13
    rts
    add     #2, r13
emit_glyph_now:
    jmp     @r14
    nop

raw_dispatch:
    mov.l   =RAW_HANDLER, r0
    jmp     @r0
    nop

dialogue_dispatch:
    sts.l   pr, @-r15
    mov.l   =DIALOGUE_MODE, r1
    mov     #1, r0
    mov.b   r0, @r1
    mov.l   =PACKED_DISPATCH, r0
    jsr     @r0
    nop
    mov.l   =DIALOGUE_MODE, r1
    mov     #0, r2
    mov.b   r2, @r1
    lds.l   @r15+, pr
    rts
    nop

raw_handler:
    sts.l   pr, @-r15
    mov     r4, r6
    mov.l   =FIRST_SPECIAL, r1
    cmp/eq  r1, r6
    bf      raw_other
    mov.l   =DEMON_ID_HANDLER, r0
    jsr     @r0
    nop
    mov.l   =EQUAL_CONTINUATION, r1
    jmp     @r1
    nop
raw_other:
    mov.l   =OTHER_CONTINUATION, r0
    jmp     @r0
    nop
    .pool
