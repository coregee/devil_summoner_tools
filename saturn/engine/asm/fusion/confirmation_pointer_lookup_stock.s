; Reviewed stock fusion-confirmation address calculation.  This is assembled
; as the expected-byte guard for the pointer-table replacement.
    mov     #40, r1
    mov.l   DESTINATION_LITERAL, r2
    mov.l   r2, @-r15
    mov     #0, r2
    mov     #0, r7
    mulu.w  r1, r8
    mov     #2, r6
    mov     #20, r5
    sts     macl, r4
    mov.l   TABLE_LITERAL, r1
    add     r1, r4
