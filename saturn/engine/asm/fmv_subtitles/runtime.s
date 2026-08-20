; Lossless START2 subtitle overlay for EVENT.BIN's Cinepak player.
;
; Both players stage a decoded frame at cached work-RAM address 0x0607704c
; before scheduling an SCU DMA to video memory.  The decoder has already done
; its cache maintenance by the time these wrappers run, so later CPU writes via
; that cached alias are not visible to the DMA engine.  Draw through the P1
; uncached alias instead; the stock transfer from 0x0607704c then sees the same
; physical bytes and carries the subtitle into the displayed frame.

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
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov.l   =UNCACHED_DECODED_FRAMEBUFFER, r14
    mov.l   =BLOCKING_ROW_STRIDE, r12
    mov     #4, r13
    bsr     fmv_present_active_frame
    nop
    mov.l   =STOCK_PRESENTER, r1
    jsr     @r1
    nop
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    rts
    mov.l   @r15+, r12
    .pool

fmv_stream_present_wrapper:
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov.l   r4, @-r15
    mov.l   r5, @-r15
    mov.l   r6, @-r15
    mov.l   =UNCACHED_DECODED_FRAMEBUFFER, r14
    mov.l   =STREAM_ROW_STRIDE, r12
    mov     #2, r13
    bsr     fmv_present_active_frame
    nop
    mov.l   @r15+, r6
    mov.l   @r15+, r5
    mov.l   @r15+, r4
    mov.l   =STOCK_STREAM_PRESENTER, r1
    jsr     @r1
    nop
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    rts
    mov.l   @r15+, r12
    .pool

fmv_present_active_frame:
    sts.l   pr, @-r15
    mov.l   =FMV_ACTIVE, r1
    mov.w   @r1, r1
    tst     r1, r1
    bt      fmv_present_active_done
    bsr     fmv_render_frame
    nop
    mov.l   =FMV_FRAME, r1
    mov.l   @r1, r2
    add     #1, r2
    mov.l   r2, @r1
fmv_present_active_done:
    lds.l   @r15+, pr
    rts
    nop
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

; Line payload: u16 x, u16 y, then one-byte dense glyph tokens. Zero ends it.
; Pointer and advance tables bind each token to an embedded FONT16 mask.
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
    mov.b   @r8+, r4
    extu.b  r4, r4
    tst     r4, r4
    bt      fmv_line_done
    add     #-1, r4
    mov     r4, r0
    mov.l   =GLYPH_ADVANCE_TABLE, r1
    mov.b   @(r0,r1), r9
    extu.b  r9, r9
    shll2   r4
    mov     r4, r0
    mov.l   =GLYPH_POINTER_TABLE, r1
    mov.l   @(r0,r1), r4
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

; r4=embedded FONT16 mask, r5=x, r6=y; r12=row bytes, r13=bytes per pixel,
; r14=base.
; Each source row is a 16-bit 1bpp mask. Draw a lower-right shadow and white
; face into either the streaming RGB555 or blocking 32-bit RGB movie buffer.
fmv_draw_glyph:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    mov     r4, r8
    mulu.w  r13, r5
    sts     macl, r5
    mulu.w  r12, r6
    sts     macl, r6
    mov     r14, r9
    add     r5, r9
    add     r6, r9
    mov     r9, r10
    add     r12, r10
    add     r13, r10
    mov     r12, r11
    mov     #16, r1
    mulu.w  r13, r1
    sts     macl, r1
    sub     r1, r11
    mov     r13, r0
    mov.l   =WHITE_PIXEL, r7
    mov.l   =SHADOW_PIXEL, r14
    mov     #-1, r5
    mov.l   =SHADOW_PIXEL_16, r6
    mov     #16, r12
fmv_glyph_row:
    mov.w   @r8+, r1
    extu.w  r1, r1
    shll16  r1
    mov     #16, r2
fmv_glyph_pixel:
    shll    r1
    bf      fmv_glyph_blank
    cmp/eq  #2, r0
    bt      fmv_glyph_pixel16
    mov.l   r14, @r10
    mov.l   r7, @r9
    bra     fmv_glyph_advance
    nop
fmv_glyph_pixel16:
    mov.w   r6, @r10
    mov.w   r5, @r9
fmv_glyph_blank:
fmv_glyph_advance:
    add     r13, r9
    add     r13, r10
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
