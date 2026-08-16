; Combat Conversation typewriter reset.
; The controller mode at 0x06073f9c is boolean: zero is confirm
; fast-forward and one is normal typewriter output.  r12 has no live value
; after 0x060593cc and the packed dispatcher preserves it, so mode + 1 is the
; visible-glyph budget for this update.

typewriter_reset:
    mov.l   TYPEWRITER_MODE_POINTER, r1
    mov.b   @r1, r1
    mov     #1, r12
    add     r1, r12
    rts
    nop
