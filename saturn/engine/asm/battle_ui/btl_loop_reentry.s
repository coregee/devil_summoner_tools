; Only the BRA word is installed. The stock `mov.b r1,@r11` delay slot at the
; following address remains in place and is shown here to make that ABI clear.

reentry:
    bra     TARGET
    mov.b   r1, @r11
