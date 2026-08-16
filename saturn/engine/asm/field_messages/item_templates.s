field_item_found:
    mov     #0, r4
    bra     field_item_message
    nop

field_item_obtained:
    mov     #1, r4
    bra     field_item_message
    nop

field_item_full:
    mov     #2, r4

field_item_message:
    mov.l   r7, @-r15
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r13
    mov     r8, r14

    mov     #1, r0
    cmp/eq  r0, r13
    bt      field_item_use_obtained
    mov     #2, r0
    cmp/eq  r0, r13
    bt      field_item_use_full
    mov.l   =FOUND_PREFIX, r10
    mov     #FOUND_PREFIX_WORDS, r9
    mov.l   =FOUND_SUFFIX, r13
    mov     #FOUND_SUFFIX_WORDS, r7
    bra     field_item_template_ready
    nop
field_item_use_obtained:
    mov.l   =OBTAINED_PREFIX, r10
    mov     #OBTAINED_PREFIX_WORDS, r9
    mov.l   =OBTAINED_SUFFIX, r13
    mov     #OBTAINED_SUFFIX_WORDS, r7
    bra     field_item_template_ready
    nop
field_item_use_full:
    mov.l   =FULL_PREFIX, r10
    mov     #FULL_PREFIX_WORDS, r9
    mov.l   =FULL_SUFFIX, r13
    mov     #FULL_SUFFIX_WORDS, r7

field_item_template_ready:
    mov.l   =BUFFER, r8
    mov     r8, r1
    mov     #0, r0
    mov     #BUFFER_WORDS, r2
field_item_clear:
    mov.w   r0, @r1
    add     #2, r1
    dt      r2
    bf      field_item_clear

    tst     r9, r9
    bt      field_item_name
field_item_copy_prefix:
    mov.w   @r10+, r0
    mov.w   r0, @r8
    add     #2, r8
    dt      r9
    bf      field_item_copy_prefix

field_item_name:
    mov     r14, r1
    add     #ITEM_FULL_NAME_OFFSET, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    mov.l   =ITEM_BASE, r12
    add     r0, r12
    mov     #ITEM_NAME_LIMIT, r11

field_item_name_loop:
    mov.b   @r12+, r0
    extu.b  r0, r0
    mov     #-1, r1
    extu.b  r1, r1
    cmp/eq  r1, r0
    bt      field_item_name_done
    mov.l   =TOKEN_MAP, r1
    shll    r0
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    tst     r0, r0
    bt      field_item_name_done
    mov.w   r0, @r8
    add     #2, r8
    dt      r11
    bf      field_item_name_loop

field_item_name_done:
    tst     r7, r7
    bt      field_item_message_done
field_item_copy_suffix:
    mov.w   @r13+, r0
    mov.w   r0, @r8
    add     #2, r8
    dt      r7
    bf      field_item_copy_suffix

field_item_message_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    mov.l   @r15+, r7
    .pool
