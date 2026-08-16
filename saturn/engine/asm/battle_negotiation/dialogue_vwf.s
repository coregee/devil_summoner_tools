; Combat Conversation's proportional dialogue renderer.
combat_render:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15

    ; The backing surface persists after its VDP1 upload.  A zero valid flag
    ; means another owner or a logical window clear invalidated its pixels, so
    ; rebuild the whole surface once.  Otherwise the high bit of each private
    ; color byte records whether that cell has already been committed.
    mov     #0, r14
    mov.l   =SURFACE_VALID, r0
    mov.b   @r0, r1
    tst     r1, r1
    bf      render_surface_ready
    mov     #1, r14
    mov.l   =ORIGINAL_SURFACE_CLEAR, r0
    jsr     @r0
    nop
render_surface_ready:
    mov     #0, r8
    mov     #0, r11

render_row:
    mov     r8, r0
    mov.w   =GRID_ROW_BYTES, r1
    mulu.w  r1, r0
    sts     macl, r0
    mov.l   =GRID, r12
    add     r0, r12

    mov     r8, r0
    mov.w   =COLOR_ROW_BYTES, r1
    mulu.w  r1, r0
    sts     macl, r0
    mov.l   =COLORS, r13
    add     r0, r13

    mov     #0, r9
    mov     #LEFT_MARGIN, r10

render_cell:
    mov.w   @r12+, r4
    extu.w  r4, r4
    mov.b   @r13, r7
    tst     r4, r4
    bt      render_next_cell

    mov.w   =ZERO_SEPARATOR_CODE, r0
    cmp/eq  r0, r4
    bt      render_zero_separator

    mov.l   =ANCHOR_CODE, r0
    cmp/eq  r0, r4
    bt      render_anchor

    mov.w   =RIGHT_MARGIN, r0
    cmp/hs  r0, r10
    bt      render_next_row
    bsr     glyph_width
    nop
    mov     r10, r5
    add     r0, r10
    mov.w   =RIGHT_MARGIN, r2
    cmp/hi  r2, r10
    bt      render_next_row
    mov     r11, r6
    tst     r14, r14
    bf      render_dirty_glyph
    cmp/pz  r7
    bf      render_next_cell
render_dirty_glyph:
    mov     #0x7f, r0
    and     r0, r7
    mov     r7, r0
    or      #0x80, r0
    mov.b   r0, @r13
    bsr     draw_one
    nop
    bra     render_next_cell
    nop

; combat_store converts a committed raw zero to a private marker so it remains
; distinguishable from unused zero-filled grid storage.  Stock COMBAT advances
; these separator cells by one fixed 16-pixel column without drawing a glyph.
render_zero_separator:
    add     #16, r10
    bra     render_next_cell
    nop

render_anchor:
    mov.w   =CHOICE_RIGHT_X, r10

render_next_cell:
    add     #1, r13
    add     #1, r9
    mov     #GRID_COLUMNS, r0
    cmp/hs  r0, r9
    bf      render_cell

render_next_row:
    add     #1, r8
    add     #16, r11
    mov     #3, r0
    cmp/hs  r0, r8
    bf      render_row

    mov.l   =SURFACE_VALID, r0
    mov     #1, r1
    mov.b   r1, @r0
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

draw_one:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11

    mov     r11, r0
    add     #1, r0
    mov.l   r0, @-r15
    mov.l   r11, @-r15
    mov.l   r8, @-r15
    mov.l   =FRAMEBUFFER_POINTER, r4
    mov.l   @r4, r4
    mov.w   =FRAMEBUFFER_STRIDE, r5
    mov     r9, r6
    mov     r10, r7
    mov.l   =SURFACE_BLITTER, r0
    jsr     @r0
    nop
    add     #12, r15

    lds.l   @r15+, pr
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

glyph_width:
    extu.w  r4, r0
    mov.l   =CODE_LIMIT, r1
    cmp/hs  r1, r0
    bt      fixed_width
    mov.l   =FONT16_POINTER, r1
    mov.l   @r1, r1
    mov.l   =WIDTH_OFFSET, r2
    add     r2, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      width_ready
fixed_width:
    mov     #16, r0
width_ready:
    rts
    nop
    .pool

; Measure the committed glyphs in one row. Returns pixel X in r0 and a
; nonzero choice-anchor flag in r1.
row_width:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     #0, r10
    mov     #LEFT_MARGIN, r11
    mov     #0, r12

row_width_loop:
    cmp/hs  r9, r10
    bt      row_width_done
    mov.w   @r8+, r4
    extu.w  r4, r4
    tst     r4, r4
    bt      row_width_next
    mov.w   =ZERO_SEPARATOR_CODE, r0
    cmp/eq  r0, r4
    bt      row_width_zero_separator
    mov.l   =ANCHOR_CODE, r0
    cmp/eq  r0, r4
    bt      row_width_anchor
    bsr     glyph_width
    nop
    add     r0, r11
    bra     row_width_next
    nop

row_width_zero_separator:
    add     #16, r11
    bra     row_width_next
    nop

row_width_anchor:
    mov.w   =CHOICE_RIGHT_X, r11
    mov     #1, r12

row_width_next:
    add     #1, r10
    bra     row_width_loop
    nop

row_width_done:
    mov     r11, r0
    mov     r12, r1
    lds.l   @r15+, pr
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

combat_store:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r6, r8

    mov.w   =MEASURE_START_CODE, r0
    cmp/eq  r0, r8
    bt      store_measure_start
    mov.w   =MEASURE_END_CODE, r0
    cmp/eq  r0, r8
    bt      store_measure_end

    tst     r8, r8
    bf      store_check_static_hint
    mov.w   =ZERO_SEPARATOR_CODE, r8

store_check_static_hint:
    mov.w   =STATIC_HINT_BASE, r0
    cmp/hs  r0, r8
    bf      store_check_measure
    mov.w   =STATIC_HINT_LIMIT, r1
    cmp/hs  r1, r8
    bt      store_check_measure
    mov     r8, r4
    sub     r0, r4
    bsr     prewrap_width
    nop
    tst     r0, r0
    bf      store_page_replay_source
    bra     store_continue
    nop

store_check_measure:
    mov.l   =MEASURE_MODE, r0
    mov.b   @r0, r1
    tst     r1, r1
    bt      store_visible
    mov     #2, r2
    cmp/eq  r2, r1
    bt      store_measure_pending
    mov     #3, r2
    cmp/eq  r2, r1
    bt      store_measure_suffix
    mov     r8, r4
    bsr     glyph_width
    nop
    mov.l   =MEASURE_WIDTH, r1
    mov.w   @r1, r2
    add     r0, r2
    mov.w   r2, @r1
    bra     store_continue
    nop

store_measure_pending:
    mov     #0, r1
    mov.b   r1, @r0
    mov.l   =MEASURE_WIDTH, r0
    mov.w   @r0, r12
    extu.w  r12, r12
    mov.l   =PENDING_BUFFER, r11
    mov     #PENDING_WORD_CAPACITY, r10

store_pending_loop:
    mov.w   @r11+, r4
    extu.w  r4, r4
    exts.w  r4, r0
    cmp/pz  r0
    bf      store_pending_done
    bsr     glyph_width
    nop
    add     r0, r12
    dt      r10
    bf      store_pending_loop
    nop

store_pending_done:
    mov     r12, r4
    bsr     prewrap_width
    nop
    tst     r0, r0
    bf      store_page_replay_pending
    bra     store_visible
    nop

store_measure_suffix:
    add     #-1, r8
    mov.l   =MEASURE_WIDTH, r0
    mov.w   r8, @r0
    mov.l   =MEASURE_MODE, r0
    mov     #2, r1
    mov.b   r1, @r0
    bra     store_continue
    nop

store_measure_start:
    mov.l   =MEASURE_MODE, r0
    mov.b   @r0, r1
    tst     r1, r1
    bt      store_measure_begin
    mov     #3, r1
    mov.b   r1, @r0
    bra     store_continue
    nop

store_measure_begin:
    mov     #1, r1
    mov.b   r1, @r0
    mov.l   =MEASURE_WIDTH, r0
    mov     #0, r1
    mov.w   r1, @r0
    bra     store_continue
    nop

store_measure_end:
    mov.l   =MEASURE_MODE, r0
    mov     #0, r1
    mov.b   r1, @r0
    mov.l   =MEASURE_WIDTH, r0
    mov.w   @r0, r4
    extu.w  r4, r4
    bsr     prewrap_width
    nop
    tst     r0, r0
    bf      store_page_replay_source
    bra     store_continue
    nop

store_visible:
    mov.w   =SOFT_WRAP_CODE, r0
    cmp/eq  r0, r8
    bf      store_glyph_ready
    mov.w   =SPACE_CODE, r8

store_glyph_ready:
    mov.l   =CURSOR_X, r1
    mov.b   @r1, r9
    extu.b  r9, r9
    mov     #GRID_COLUMNS, r0
    cmp/hs  r0, r9
    bt      store_visible_normal
    mov.l   =CURSOR_Y, r3
    mov.b   @r3, r10
    extu.b  r10, r10
    mov     #3, r0
    cmp/hs  r0, r10
    bf      store_row_ready
    mov     #2, r10

store_row_ready:
    mov     r10, r0
    mov.w   =GRID_ROW_BYTES, r4
    mulu.w  r4, r0
    sts     macl, r0
    mov.l   =GRID, r4
    add     r0, r4
    mov     r9, r0
    add     r9, r0
    bsr     invalidate_occupied_cell
    nop
    mov.w   r8, @(r0,r4)

    mov     r10, r0
    mov.w   =COLOR_ROW_BYTES, r4
    mulu.w  r4, r0
    sts     macl, r0
    mov.l   =COLORS, r4
    add     r0, r4
    mov.l   =CURRENT_COLOR, r0
    mov.b   @r0, r3
    mov     r3, r0
    and     #0x7f, r0
    mov     r0, r3
    mov     r9, r0
    mov.b   r3, @(r0,r4)
    add     #1, r9
    mov.l   =CURSOR_X, r1
    mov.b   r9, @r1
    bra     store_visible_return
    nop

store_page_replay_source:
    mov.l   =SOURCE_POINTER, r1
    mov.l   @r1, r2
    add     #-2, r2
    mov.l   r2, @r1
    bra     store_page_return
    nop

store_page_replay_pending:
    mov.l   =PENDING_FLAG, r1
    mov     #0, r2
    mov.w   r2, @r1

store_page_return:
    bra     store_return_status
    mov     #-2, r0

store_visible_return:
store_visible_normal:
    mov     #1, r0
    bra     store_return_status
    nop
store_continue:
    mov     #-1, r0
store_return_status:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =STORE_RETURN, r1
    jmp     @r1
    nop
    .pool

; Decide the row from a complete width hint before any visible glyph is stored.
prewrap_width:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov.l   =CURSOR_X, r0
    mov.b   @r0, r9
    extu.b  r9, r9
    tst     r9, r9
    bt      prewrap_done
    mov.l   =CURSOR_Y, r0
    mov.b   @r0, r10
    extu.b  r10, r10
    mov     #3, r0
    cmp/hs  r0, r10
    bt      prewrap_page
    mov     r10, r0
    mov.w   =GRID_ROW_BYTES, r1
    mulu.w  r1, r0
    sts     macl, r0
    mov.l   =GRID, r4
    add     r0, r4
    mov     r9, r5
    bsr     row_width
    nop
    tst     r1, r1
    bf      prewrap_done
    add     r8, r0
    mov.w   =RIGHT_MARGIN, r1
    cmp/hi  r1, r0
    bf      prewrap_done
    mov     #2, r0
    cmp/hs  r0, r10
    bt      prewrap_page
    add     #1, r10
    mov.l   =CURSOR_Y, r0
    mov.b   r10, @r0
    mov.l   =CURSOR_X, r0
    mov     #0, r1
    mov.b   r1, @r0
prewrap_done:
    mov     #0, r0
    bra     prewrap_return
    nop
prewrap_page:
    mov     #1, r0
prewrap_return:
    lds.l   @r15+, pr
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
combat_clear:
    mov.l   r8, @-r15
    mov.l   =CURSOR_X, r1
    mov     #0, r0
    mov.b   r0, @r1
    mov.l   =SURFACE_VALID, r1
    mov.b   r0, @r1
    mov.l   =CURSOR_Y, r1
    mov.b   r0, @r1
    mov.l   =MEASURE_MODE, r1
    mov.b   r0, @r1
    mov.l   =MEASURE_WIDTH, r1
    mov.w   r0, @r1
    mov.l   =GRID, r1
    mov.l   =COLORS, r2
    mov.w   =TOTAL_CELLS, r8
clear_loop:
    mov.w   r0, @r1
    add     #2, r1
    mov.b   r0, @r2
    add     #1, r2
    dt      r8
    bf      clear_loop
    rts
    mov.l   @r15+, r8

combat_clear_options:
    mov.l   r8, @-r15
    mov.l   =CURSOR_X, r1
    mov     #0, r0
    mov.b   r0, @r1
    mov.l   =SURFACE_VALID, r1
    mov.b   r0, @r1
    mov.l   =CURSOR_Y, r1
    mov.b   r0, @r1
    mov.l   =MEASURE_MODE, r1
    mov.b   r0, @r1
    mov.l   =MEASURE_WIDTH, r1
    mov.w   r0, @r1
    mov.l   =GRID, r1
    mov.w   =GRID_ROW_BYTES, r2
    add     r2, r1
    mov.l   =COLORS, r2
    mov.w   =COLOR_ROW_BYTES, r3
    add     r3, r2
    mov.w   =OPTION_CELLS, r8
clear_options_loop:
    mov.w   r0, @r1
    add     #2, r1
    mov.b   r0, @r2
    add     #1, r2
    dt      r8
    bf      clear_options_loop
    rts
    mov.l   @r15+, r8

combat_choice_position:
    mov.l   =MEASURE_MODE, r3
    mov     #0, r2
    mov.b   r2, @r3
    mov.l   =MEASURE_WIDTH, r3
    mov.w   r2, @r3
    mov     r4, r0
    mov     #1, r1
    and     r0, r1
    mov     #ANCHOR_COLUMN, r2
    mul.l   r1, r2
    sts     macl, r2
    add     #1, r2
    mov.l   =CURSOR_X, r3
    mov.b   r2, @r3

    and     #2, r0
    shlr    r0
    add     #1, r0
    mov.l   =CURSOR_Y, r3
    mov.b   r0, @r3

    tst     r1, r1
    bt      choice_position_done
    mov.w   =GRID_ROW_BYTES, r2
    mulu.w  r2, r0
    sts     macl, r0
    mov.l   =GRID, r2
    add     r0, r2
    mov.w   =ANCHOR_BYTE_OFFSET, r0
    add     r0, r2
    mov.l   =ANCHOR_CODE, r0
    mov.w   r0, @r2
choice_position_done:
    rts
    nop

; Two non-dialogue combat renderers share this backing surface and call the
; stock clear through pointer literals.  Invalidate our retained-cell markers
; before tail-calling the original clear so the next dialogue render rebuilds.
combat_external_surface_clear:
    mov.l   =SURFACE_VALID, r1
    mov     #0, r0
    mov.b   r0, @r1
    mov.l   =ORIGINAL_SURFACE_CLEAR, r1
    jmp     @r1
    nop

; Normal stores append into empty cells.  If a caller reuses an occupied cell
; without a logical clear, force one authoritative surface replay so pixels
; belonging only to the old glyph cannot survive the replacement.
invalidate_occupied_cell:
    mov.w   @(r0,r4), r1
    tst     r1, r1
    bt      occupied_cell_done
    mov.l   =SURFACE_VALID, r1
    mov     #0, r2
    mov.b   r2, @r1
occupied_cell_done:
    rts
    nop
    .pool
