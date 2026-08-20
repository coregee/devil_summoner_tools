; COMBAT constructs the two sentinel party-panel rows on its stack. Keep the
; stock register reuse and exact 5/8-cell layout while sourcing every glyph
; from the authored party-panel asset.

    mov     #EMPTY0, r1
    mov.b   r1, @r15
    mov     r15, r2
    add     #1, r2
    mov     #EMPTY1, r1
    mov.b   r1, @r2
    mov     r15, r1
    add     #2, r1
    mov     #EMPTY2, r3
    mov.b   r3, @r1
    mov     r15, r1
    add     #3, r1
    mov     #EMPTY3, r6
    mov.b   r6, @r1
    mov     r15, r1
    add     #4, r1
    mov     #EMPTY4, r7
    mov.b   r7, @r1

    mov     r15, r2
    add     #8, r2
    mov     #IN_PARTY0, r1
    mov.b   r1, @r2
    mov     r15, r2
    add     #9, r2
    mov     #IN_PARTY1, r1
    mov.b   r1, @r2
    mov     r15, r2
    add     #10, r2
    mov     #IN_PARTY2, r1
    mov.b   r1, @r2
    mov     r15, r1
    add     #11, r1
    mov.b   r3, @r1
    mov     r15, r2
    add     #12, r2
    mov     #IN_PARTY4, r1
    mov.b   r1, @r2
    mov     r15, r2
    add     #13, r2
    mov     #IN_PARTY5, r1
    mov.b   r1, @r2
    mov     r15, r1
    add     #14, r1
    mov.b   r6, @r1
    mov     r15, r1
    add     #15, r1
    mov.b   r7, @r1
