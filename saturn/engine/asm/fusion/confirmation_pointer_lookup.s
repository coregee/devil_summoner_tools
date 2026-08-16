; The stock code multiplies the selected row by a 40-byte stride.  English
; confirmation rows have independent capacities, so resolve them through the
; aligned four-entry pointer table instead.
    mov.l   DESTINATION_LITERAL, r2
    mov.l   r2, @-r15
    mov     #0, r2
    mov     #0, r7
    mov     #2, r6
    mov     #20, r5
    mov     r8, r0
    shll2   r0
    mov.l   TABLE_LITERAL, r1
    add     #POINTER_TABLE_OFFSET, r1
    mov.l   @(r0,r1), r4
