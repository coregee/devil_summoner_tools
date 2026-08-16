skill_dispatcher:
    mov.l   =MAGIC_FIRST, r0
    cmp/hs  r0, r4
    bf      skill_fallback
    mov.l   =MAGIC_END, r0
    cmp/hs  r0, r4
    bt      skill_fallback
    add     #NAME_POINTER, r4
    mov.w   @r4, r0
    extu.w  r0, r0
    mov.l   =MAGIC_BASE, r4
    add     r0, r4
    mov     #32, r5
    mov.l   =FONT8_VWF, r0
    jmp     @r0
    nop
skill_fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
