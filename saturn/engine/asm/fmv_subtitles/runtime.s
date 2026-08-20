; Lossless START2 subtitle overlay for EVENT.BIN's Cinepak player.
;
; The stock presenter writes a 32-bit RGB frame to the NBG0 bitmap at
; 0x25e08000.  The wrapped presenter calls that routine first, then draws the
; active cue directly into the fresh frame.  A subsequent movie frame replaces
; every subtitle pixel, so gaps and cleanup need no destructive clear pass.

fmv_blocking_player_wrapper:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =FMV_ACTIVE, r1
    mov     #START2_INDEX, r0
    cmp/eq  r10, r0
    mov     #0, r2
    bf      fmv_blocking_state_ready
    mov     #1, r2
fmv_blocking_state_ready:
    mov.w   r2, @r1
    mov.l   =FMV_FRAME, r1
    mov     #0, r2
    mov.l   r2, @r1
    mov.l   =STOCK_BLOCKING_PLAYER, r1
    jsr     @r1
    nop
    mov     r0, r8
    mov.l   =FMV_ACTIVE, r1
    mov     #0, r2
    mov.w   r2, @r1
    mov     r8, r0
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

fmv_async_init_wrapper:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =ASYNC_MOVIE_INDEX, r1
    mov.w   @r1, r2
    extu.w  r2, r2
    mov     #START2_INDEX, r0
    cmp/eq  r2, r0
    mov     #0, r2
    bf      fmv_async_state_ready
    mov     #1, r2
fmv_async_state_ready:
    mov.l   =FMV_ACTIVE, r1
    mov.w   r2, @r1
    mov.l   =FMV_FRAME, r1
    mov     #0, r2
    mov.l   r2, @r1
    mov.l   =STOCK_ASYNC_INIT, r1
    jsr     @r1
    nop
    mov     r0, r8
    mov     r8, r0
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

fmv_present_wrapper:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =STOCK_PRESENTER, r1
    jsr     @r1
    nop
    mov     r0, r8
    mov.l   =FMV_ACTIVE, r1
    mov.w   @r1, r1
    tst     r1, r1
    bt      fmv_present_done
    bsr     fmv_render_frame
    nop
    mov.l   =FMV_FRAME, r1
    mov.l   @r1, r2
    add     #1, r2
    mov.l   r2, @r1
fmv_present_done:
    mov     r8, r0
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

; Cue table:
;   u16 count, u16 reserved
;   repeated {u16 start, u16 end, u32 line_1, u32 line_2_or_zero}
fmv_render_frame:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    sts.l   pr, @-r15
    mov.l   =FMV_FRAME, r1
    mov.l   @r1, r8
    mov.l   =FMV_CUE_TABLE, r9
    mov.w   @r9+, r10
    extu.w  r10, r10
    add     #2, r9
fmv_cue_loop:
    mov.w   @r9, r1
    extu.w  r1, r1
    cmp/hs  r1, r8
    bf      fmv_next_cue
    mov     r9, r0
    add     #2, r0
    mov.w   @r0, r1
    extu.w  r1, r1
    cmp/hs  r1, r8
    bt      fmv_next_cue
    mov.l   @(4,r9), r4
    bsr     fmv_draw_line
    nop
    mov.l   @(8,r9), r4
    tst     r4, r4
    bt      fmv_render_done
    bsr     fmv_draw_line
    nop
    bra     fmv_render_done
    nop
fmv_next_cue:
    add     #12, r9
    dt      r10
    bf      fmv_cue_loop
fmv_render_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; Line payload: u16 x, u16 y, then packed FONT16 words.  Bits 15..12 hold
; the proportional advance and bits 11..0 hold the atlas code.  Zero ends it.
fmv_draw_line:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov.w   @r8+, r10
    extu.w  r10, r10
    mov.w   @r8+, r11
    extu.w  r11, r11
fmv_line_loop:
    mov.w   @r8+, r4
    extu.w  r4, r4
    tst     r4, r4
    bt      fmv_line_done
    mov     r4, r9
    shlr8   r9
    shlr2   r9
    shlr2   r9
    mov     r4, r0
    shll8   r0
    shll2   r0
    shll2   r0
    shlr8   r0
    shlr2   r0
    shlr2   r0
    mov     r0, r4
    mov     r10, r5
    bsr     fmv_draw_glyph
    mov     r11, r6
    add     r9, r10
    bra     fmv_line_loop
    nop
fmv_line_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

; r4=FONT16 code, r5=x, r6=y.  Each source row is a 16-bit 1bpp mask.
; Draw a one-pixel black lower-right shadow and an opaque white face into the
; movie's 512-pixel-stride, 32-bit RGB NBG0 bitmap.
fmv_draw_glyph:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    extu.w  r4, r4
    shll2   r4
    shll2   r4
    shll    r4
    mov.l   =FONT16_BITMAP, r8
    add     r4, r8
    extu.w  r5, r5
    shll2   r5
    extu.w  r6, r6
    shll8   r6
    shll2   r6
    shll    r6
    mov.l   =MOVIE_FRAMEBUFFER, r9
    add     r5, r9
    add     r6, r9
    mov     r9, r10
    mov.l   =SHADOW_OFFSET, r1
    add     r1, r10
    mov.l   =ROW_ADVANCE, r11
    mov.l   =WHITE_PIXEL, r13
    mov.l   =SHADOW_PIXEL, r14
    mov     #16, r12
fmv_glyph_row:
    mov.w   @r8+, r1
    extu.w  r1, r1
    mov     #16, r2
fmv_glyph_pixel:
    shll    r1
    bf      fmv_glyph_blank
    mov.l   r14, @r10
    mov.l   r13, @r9
fmv_glyph_blank:
    add     #4, r9
    add     #4, r10
    dt      r2
    bf      fmv_glyph_pixel
    add     r11, r9
    add     r11, r10
    dt      r12
    bf      fmv_glyph_row
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
