; Combat Conversation visible-glyph typewriter step.
; Mode zero starts with a budget of one and therefore takes the stock visible
; return.  Normal mode starts with two and re-enters the pending/source
; selector exactly once.

typewriter_visible:
    dt      r12
    bf      TYPEWRITER_PENDING_SELECTOR
    bra     TYPEWRITER_FRAME_RETURN
    nop
