
; ===== dispatch router (replaces the type-cmp chain head) =================
; entry: r0 = field type (extu.b); r11-r14 = live sprite regs (preserve)
router:
    cmp/eq  #6, r0
    bt      r_occ
    cmp/eq  #11, r0
    bt      r_conf
    cmp/eq  #12, r0
    bt      r_t12
    tst     r0, r0
    bt      r_idle
    mov     #6, r1
    cmp/hs  r1, r0              ; unknown high types -> idle
    bt      r_idle
    mov.l   =g_state, r1        ; text field 1-5: dispatch on UI state
    mov.b   @r1, r1
    extu.b  r1, r1
    mov     r1, r0
    cmp/eq  #5, r0
    bt      r_tabsel
    cmp/eq  #6, r0
    bt      r_grid
    mov.l   =J_TEXT_SKIP, r1    ; no handler this frame (dead state 0 etc.)
    mov     #127, r7
    jmp     @r1
    nop
r_tabsel:
    mov.l   =tabsel, r1
    bra     r_go
    nop
r_grid:
    mov.l   =grid_handler, r1
r_go:
    mov.l   =J_TEXT_JSR, r2
    jmp     @r2
    nop
r_occ:
    mov.l   =J_OCC, r1
    jmp     @r1
    nop
r_conf:
    mov.l   =J_CONFIRM, r1
    jmp     @r1
    nop
r_t12:
    mov.l   =J_T12, r1
    jmp     @r1
    nop
r_idle:
    mov.l   =J_IDLE, r1
    jmp     @r1
    nop
    .pool

; ===== small helpers ========================================================
; stage_of: r4 = field type 1-5 -> r0 = NAME_ASCII row ptr. clobbers r0,r1.
stage_of:
    mov.l   =stage_ptrs, r1
    mov     r4, r0
    add     #-1, r0
    shll2   r0
    mov.l   @(r0,r1), r0
    rts
    nop

; centered_draw8(r4=8-byte ASCII, r5=cell x, r6=y, r7=color): draw each Ark
; FONT16 glyph horizontally centered in its 16px cursor cell. Blank bytes still
; consume one cell. This preserves the stock cursor geometry without imposing
; the stock renderer's left-aligned 16px advance on the glyph bitmap.
centered_draw8:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
    mov     #8, r12
cd8_loop:
    mov.b   @r8+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      cd8_next
    add     #-32, r0
    mov     r0, r13
    mov.l   =ascii_to_width, r1
    mov.b   @(r0,r1), r1
    extu.b  r1, r1
    mov     #16, r5
    sub     r1, r5
    shlr    r5
    add     r9, r5
    mov     r13, r0
    shll    r0
    mov.l   =ascii_to_atlas, r1
    mov.w   @(r0,r1), r4
    extu.w  r4, r4
    mov     r10, r6
    mov     r11, r7
    mov     r11, r0
    add     #1, r0
    mov.l   r0, @-r15
    mov.l   =fn_blit, r1
    jsr     @r1
    nop
    add     #4, r15
cd8_next:
    add     #16, r9
    dt      r12
    bf      cd8_loop
    lds.l   @r15+, pr
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

; echo_redraw(r4=field type 1-5): VWF question + fixed-cell answer on row 8.
echo_redraw:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    extu.b  r4, r8
    tst     r8, r8
    bt      er_done
    mov     #6, r1
    cmp/hs  r1, r8
    bt      er_done
    mov.l   =fn_rowclear, r1    ; clear stock row-8 codes/colors
    jsr     @r1
    mov     #8, r4
    mov.l   =fn_clearrow, r1    ; direct pixel draws also need the canvas cleared
    jsr     @r1
    mov     #8, r4
    mov     r8, r4
    bsr     stage_of
    nop
    mov     r0, r4
    mov     #88, r5
    shll    r5                  ; cell 11 begins at x = 176
    mov     #8, r6
    shll2   r6
    shll2   r6                  ; y = 128 (row 8)
    mov     #2, r7
    bsr     centered_draw8
    nop
    mov     r8, r0
    add     #-1, r0
    shll2   r0
    mov.l   =prompt_pointers, r1
    mov.l   @(r0,r1), r4
    mov     #8, r5
    mov     #8, r6
    shll2   r6
    shll2   r6                  ; y = 128 (row 8)
    mov     #2, r7
    bsr     prop_draw
    nop
    mov.l   =fn_upload, r1
    jsr     @r1
    nop
er_done:
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8

; ===== field_open: r4 = field type. VWF prompt + fixed-cell answer =========
field_open:
    sts.l   pr, @-r15
    bsr     echo_redraw
    nop
    lds.l   @r15+, pr
    rts
    nop

; initial_row_flush(r4=row): preserve the stock screen constructor's row
; flush, then add the first VWF prompt after row 8's blank fixed-cell template
; has been copied to the canvas.
initial_row_flush:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov.l   =fn_rowflush, r1
    jsr     @r1
    nop
    mov     r8, r0
    cmp/eq  #8, r0
    bf      irf_done
    mov.l   =prompt_pointers, r1
    mov.l   @r1, r4
    mov     #8, r5
    mov     #8, r6
    shll2   r6
    shll2   r6                  ; y = 128 (row 8)
    mov     #2, r7
    bsr     prop_draw
    nop
irf_done:
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

; ===== advance / backspace ==================================================
advance:
    sts.l   pr, @-r15
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #62, r4
    mov.l   =g_pos, r2
    mov.w   @r2, r1
    extu.w  r1, r0
    cmp/eq  #7, r0
    bt      adv_park
    add     #1, r1
    mov.w   r1, @r2
    lds.l   @r15+, pr
    rts
    nop
adv_park:
    mov.l   =g_col, r2          ; park cursor on the END cell (15,4)
    mov     #15, r1
    mov.w   r1, @r2
    mov.l   =g_row, r2
    mov     #4, r1
    mov.w   r1, @r2
    lds.l   @r15+, pr
    rts
    nop

backspace:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #61, r4
    mov.l   =g_pos, r2
    mov.w   @r2, r1
    extu.w  r1, r1
    tst     r1, r1
    bt      bk_done
    add     #-1, r1
    mov.w   r1, @r2
    mov     r1, r8
    mov.l   =g_type, r4         ; erase the staged byte and redraw its VWF row
    mov.b   @r4, r4
    extu.b  r4, r4
    bsr     stage_of
    nop
    add     r8, r0
    mov     #0, r1
    mov.b   r1, @r0
    bsr     echo_redraw
    nop
bk_done:
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

; ===== grid handler (state 6, field types 1-5) =============================
grid_handler:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    sts.l   pr, @-r15
    mov.l   =fn_btnA, r0        ; A pressed? (mask & edge == 0 = pressed)
    jsr     @r0
    nop
    mov.l   =g_pad_edge, r1
    mov.w   @r1, r1
    and     r1, r0
    extu.w  r0, r0
    tst     r0, r0
    bf      gh_notA
    mov.l   =g_row, r1          ; === A: fetch grid cell ===
    mov.w   @r1, r2
    extu.w  r2, r2
    mov.l   =g_col, r1
    mov.w   @r1, r7
    extu.w  r7, r7
    mov     #19, r1
    mul.l   r1, r2
    sts     macl, r1
    add     r7, r1
    add     r1, r1              ; r1 = (row*19+col)*2
    mov.l   =g_tab, r3
    mov.b   @r3, r3
    extu.b  r3, r3
    add     #-7, r3
    mov     #2, r0
    cmp/hi  r0, r3
    bf      gh_tabok
    mov     #0, r3
gh_tabok:
    shll2   r3
    shll    r3
    mov.l   =grid_bases, r2
    add     r3, r2              ; r2 -> {disp, comm} pair
    mov.l   @r2, r3
    mov     r1, r0
    mov.w   @(r0,r3), r3        ; display cell code
    extu.w  r3, r0
    mov.w   =0x01F7, r3
    cmp/eq  r3, r0
    bt      gh_end
    cmp/eq  #103, r0
    bt      gh_adv
    cmp/eq  #104, r0
    bt      gh_bksp
    mov.l   @(4,r2), r3         ; commit table -> ascii
    mov     r1, r0
    mov.w   @(r0,r3), r9
    extu.w  r9, r9
    mov.l   =g_type, r4         ; stage ascii byte
    mov.b   @r4, r4
    extu.b  r4, r4
    bsr     stage_of
    nop
    mov.l   =g_pos, r1
    mov.w   @r1, r1
    extu.w  r1, r1
    mov     r0, r3
    add     r1, r3
    mov.b   r9, @r3
    bsr     echo_redraw
    nop
    bsr     advance
    nop
    bra     gh_done
    nop
gh_end:
    bsr     end_handler
    nop
    bra     gh_done
    nop
gh_adv:
    bsr     advance
    nop
    bra     gh_done
    nop
gh_bksp:
    bsr     backspace
    nop
    bra     gh_done
    nop
gh_notA:
    mov.l   =fn_btnB, r0        ; B = backspace
    jsr     @r0
    nop
    mov.l   =g_pad_edge, r1
    mov.w   @r1, r1
    and     r1, r0
    extu.w  r0, r0
    tst     r0, r0
    bt      gh_bksp
    mov.l   =fn_btnX, r0        ; exit-to-tabs button
    jsr     @r0
    nop
    mov.l   =g_pad_edge, r1
    mov.w   @r1, r2
    and     r2, r0
    extu.w  r0, r0
    tst     r0, r0
    bf      gh_move
    mov.l   =fn_sound, r1       ; exit to tab row. NOT fn_exitgrid (0x06030e84):
    jsr     @r1                 ; that redraws tab-7 via the kanji drawer (autocolor)
    mov     #63, r4             ; which colours our Latin (codes <=0x168) blue. Just
    mov.l   =g_state, r2        ; sound + state:=5; re-entry (tabsel) resets col/row.
    mov     #5, r1
    mov.b   r1, @r2
    bra     gh_done
    nop
gh_move:
    mov.w   =0x0800, r1         ; START edge -> park cursor on END (quick finish)
    and     r2, r1
    tst     r1, r1
    bf      gh_notstart
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #62, r4
    mov.l   =g_col, r1
    mov     #15, r0
    mov.w   r0, @r1
    mov.l   =g_row, r1
    mov     #4, r0
    mov.w   r0, @r1
    bra     gh_done
    nop
gh_notstart:
    mov.w   =0x1000, r1         ; UP edge on row 1 -> back to tab row
    and     r2, r1
    tst     r1, r1
    bf      gh_uprep
    mov.l   =g_row, r1
    mov.w   @r1, r1
    extu.w  r1, r0
    cmp/eq  #1, r0
    bf      gh_uprep
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #60, r4
    mov.l   =g_state, r2
    mov     #5, r1
    bra     gh_done
    mov.b   r1, @r2
gh_uprep:
    mov.l   =g_pad_rep, r1      ; held-repeat movement
    mov.w   @r1, r3
    mov.w   =0x1000, r1
    and     r3, r1
    tst     r1, r1
    bf      gh_down
    mov.l   =g_row, r2
    mov.w   @r2, r1
    extu.w  r1, r0
    cmp/eq  #1, r0
    bt      gh_done
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #60, r4
    mov.l   =g_row, r2
    mov.w   @r2, r1
    add     #-1, r1
    bra     gh_done
    mov.w   r1, @r2
gh_down:
    mov.w   =0x2000, r1
    and     r3, r1
    tst     r1, r1
    bf      gh_right
    mov.l   =g_row, r2
    mov.w   @r2, r1
    extu.w  r1, r1
    mov     #3, r0
    cmp/hi  r0, r1
    bt      gh_done
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #60, r4
    mov.l   =g_row, r2
    mov.w   @r2, r1
    add     #1, r1
    bra     gh_done
    mov.w   r1, @r2
gh_right:
    mov.l   =0x00008000, r1
    and     r3, r1
    tst     r1, r1
    bf      gh_left
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #60, r4
    mov.l   =g_col, r2
    mov.w   @r2, r1
    extu.w  r1, r0
    cmp/eq  #15, r0
    bf/s    gh_rstore
    add     #1, r1
    mov     #3, r1
gh_rstore:
    bra     gh_done
    mov.w   r1, @r2
gh_left:
    mov.w   =0x4000, r1
    and     r3, r1
    tst     r1, r1
    bf      gh_done
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #60, r4
    mov.l   =g_col, r2
    mov.w   @r2, r1
    extu.w  r1, r0
    cmp/eq  #3, r0
    bf/s    gh_lstore
    add     #-1, r1
    mov     #15, r1
gh_lstore:
    mov.w   r1, @r2
gh_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; ===== tab-select (state 5) =================================================
tabsel:
    sts.l   pr, @-r15
    mov.l   =fn_btnA, r0
    jsr     @r0
    nop
    mov.l   =g_pad_edge, r1
    mov.w   @r1, r1
    and     r1, r0
    extu.w  r0, r0
    tst     r0, r0
    bt      ts_enter
    mov.l   =g_pad_edge, r1
    mov.w   @r1, r2
    mov.w   =0x2000, r1         ; DOWN also enters the grid
    and     r2, r1
    tst     r1, r1
    bt      ts_enter
    mov.l   =0x00008000, r1     ; RIGHT: next tab
    and     r2, r1
    tst     r1, r1
    bt      ts_right
    mov.w   =0x4000, r1         ; LEFT: previous tab
    and     r2, r1
    tst     r1, r1
    bt      ts_left
    lds.l   @r15+, pr
    rts
    nop
ts_enter:
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #62, r4
    mov.l   =g_state, r2
    mov     #6, r1
    mov.b   r1, @r2
    mov.l   =g_col, r2
    mov     #3, r1
    mov.w   r1, @r2
    mov.l   =g_row, r2
    mov     #1, r1
    mov.w   r1, @r2
    lds.l   @r15+, pr
    rts
    nop
ts_right:
    mov.l   =g_tab, r2
    mov.b   @r2, r1
    extu.b  r1, r0
    cmp/eq  #9, r0
    bf/s    ts_rs
    add     #1, r1
    mov     #7, r1
ts_rs:
    bra     ts_redraw
    mov.b   r1, @r2
ts_left:
    mov.l   =g_tab, r2
    mov.b   @r2, r1
    extu.b  r1, r0
    cmp/eq  #7, r0
    bf/s    ts_ls
    add     #-1, r1
    mov     #9, r1
ts_ls:
    mov.b   r1, @r2
ts_redraw:
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #60, r4
    bsr     grid_draw
    nop
    mov.l   =g_type, r1
    mov.b   @r1, r4
    extu.b  r4, r4
    bsr     echo_redraw          ; restore the question after the grid upload
    nop
    lds.l   @r15+, pr
    rts
    nop

; ===== grid drawer (tab-aware; runtime-centers KANJI glyphs in each cell) ===
grid_draw:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov.l   =fn_clear07, r1
    jsr     @r1
    nop
    mov.l   =g_tab, r1
    mov.b   @r1, r1
    extu.b  r1, r1
    add     #-7, r1
    mov     #2, r0
    cmp/hi  r0, r1
    bf      gd_ok
    mov     #0, r1
gd_ok:
    shll2   r1
    shll    r1
    mov.l   =grid_bases, r2
    add     r1, r2
    mov.l   @r2, r10           ; display words (KANJI codes)
    mov.l   @(4,r2), r11       ; commit words (ASCII used for ink offsets)
    mov     #8, r8
    mov     #0, r12            ; pixel y
gd_row:
    mov     #0, r9             ; column
gd_cell:
    mov.w   @r10, r14
    extu.w  r14, r14
    tst     r14, r14
    bt      gd_next
    mov     r9, r5
    shll2   r5
    shll2   r5                 ; cell x = column * 16
    mov.w   @r11, r0
    extu.w  r0, r0
    tst     r0, r0             ; END has no ASCII/offset entry
    bt      gd_color
    add     #-32, r0
    mov.l   =ascii_to_grid_offset, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    add     r0, r5             ; runtime horizontal centering
gd_color:
    mov     #2, r7             ; ordinary grid glyphs are white
    mov.w   =0x01F7, r1
    cmp/eq  r1, r14
    bf      gd_blit
    mov     #10, r7            ; END remains green
gd_blit:
    mov     r14, r4
    mov     r12, r6
    mov     r7, r0
    add     #1, r0
    mov.l   r0, @-r15          ; shadow color
    mov.l   =fn_kanji_blit, r1
    jsr     @r1
    nop
    add     #4, r15
gd_next:
    add     #2, r10
    add     #2, r11
    add     #1, r9
    mov     r9, r0
    cmp/eq  #19, r0
    bf      gd_cell
    dt      r8
    bt      gd_flush
    bra     gd_row
    add     #16, r12
gd_flush:
    mov.l   =fn_upload, r1
    jsr     @r1
    nop
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

; ===== init shim (screen open: EN defaults + first grid) ===================
init_shim:
    sts.l   pr, @-r15
    mov.l   =default_city_ward, r1
    mov.l   =DEF_CITY, r2       ; city+ward rows are contiguous (16 B)
    mov     #16, r3
is_copy:
    mov.b   @r1+, r0
    mov.b   r0, @r2
    add     #1, r2
    dt      r3
    bf      is_copy
    bsr     grid_draw
    nop
    lds.l   @r15+, pr
    rts
    nop
    .pool

; ===== END handler (field sequencer) ========================================
end_handler:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov.l   =g_type, r1
    mov.b   @r1, r1
    extu.b  r1, r8
    mov     r8, r0
    mov     #6, r1
    cmp/hs  r1, r0
    bt      eh_hi
    mov     r8, r4              ; empty check: all cells 0/space -> buzz
    bsr     stage_of
    nop
    mov     r0, r9
    mov     #8, r2
eh_scan:
    mov.b   @r9+, r1
    extu.b  r1, r0
    tst     r0, r0
    bt      eh_next
    cmp/eq  #0x20, r0
    bf      eh_ok
eh_next:
    dt      r2
    bf      eh_scan
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #64, r4
    bra     eh_done
    nop
eh_ok:
    mov.l   =fn_sound, r1
    jsr     @r1
    mov     #62, r4
    mov     #0, r1
    mov.l   =g_pos, r2
    mov.w   r1, @r2
    mov.l   =g_scroll, r2
    mov.w   r1, @r2
    mov     r8, r0
    cmp/eq  #5, r0
    bt      eh_to_occ
    add     #1, r8              ; -> next text field
    mov.l   =g_type, r1
    mov.b   r8, @r1
    mov.l   =g_state, r1
    mov     #5, r2
    mov.b   r2, @r1
    mov.l   =g_tab, r1
    mov     #7, r2
    mov.b   r2, @r1
    mov.l   =g_col, r1
    mov     #3, r2
    mov.w   r2, @r1
    mov.l   =g_row, r1
    mov     #1, r2
    mov.w   r2, @r1
    bsr     grid_draw
    nop
    mov     r8, r4
    bsr     field_open          ; prompt is the final layer uploaded on transition
    nop
    bra     eh_done
    nop
eh_to_occ:
    mov     #6, r2              ; ward done -> occupation (type 6, state 6)
    mov.l   =g_type, r1
    mov.b   r2, @r1
    mov.l   =g_state, r1
    mov.b   r2, @r1
    mov.l   =g_tab, r1
    mov     #4, r2
    mov.b   r2, @r1
    mov.l   =g_col, r1
    mov     #4, r2
    mov.w   r2, @r1
    mov.l   =g_row, r1
    mov     #1, r2
    mov.w   r2, @r1
    mov     #0, r0             ; occ_last = 0, draw with choice 0 highlighted
    mov.l   =occ_last, r1
    mov.w   r0, @r1
    mov.l   =fn_rowclear, r1    ; retire the editable row before occupation
    jsr     @r1
    mov     #8, r4
    mov.l   =fn_clearrow, r1
    jsr     @r1
    mov     #8, r4
    mov     #0, r4
    mov.l   =occ_draw, r1
    jsr     @r1
    nop
    bra     eh_done
    nop
eh_hi:
    mov     r8, r0
    cmp/eq  #6, r0
    bt      eh_occ_end
    cmp/eq  #11, r0
    bt      eh_redo
    bra     eh_done
    nop
eh_occ_end:
    mov.l   =fn_sound, r1       ; occupation chosen -> confirm screen
    jsr     @r1
    mov     #62, r4
    mov     #0, r1
    mov.l   =g_pos, r2
    mov.w   r1, @r2
    mov.l   =g_col, r2
    mov.w   r1, @r2
    mov.l   =g_row, r2
    mov.w   r1, @r2
    mov     #11, r1
    mov.l   =g_type, r2
    mov.b   r1, @r2
    bsr     confirm_open
    nop
    bra     eh_done
    nop
eh_redo:
    mov.l   =fn_sound, r1       ; confirm NO -> restart at field 1
    jsr     @r1
    mov     #62, r4
    mov     #1, r1
    mov.l   =g_type, r2
    mov.b   r1, @r2
    mov.l   =g_state, r2
    mov     #5, r1
    mov.b   r1, @r2
    mov.l   =g_tab, r2
    mov     #7, r1
    mov.b   r1, @r2
    mov.l   =g_col, r2
    mov     #3, r1
    mov.w   r1, @r2
    mov.l   =g_row, r2
    mov     #1, r1
    mov.w   r1, @r2
    mov     #0, r1
    mov.l   =g_pos, r2
    mov.w   r1, @r2
    bsr     grid_draw
    nop
    mov     #1, r4
    bsr     field_open          ; prompt is the final layer uploaded on restart
    nop
eh_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; ===== confirm_open: VWF summary rows plus proportional row-12 choices =====
confirm_open:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     #8, r8
co_clear:
    mov.l   =fn_clearrow, r1
    jsr     @r1
    mov     r8, r4
    add     #1, r8
    mov     r8, r0
    cmp/eq  #11, r0
    bf      co_clear
    mov.l   =fn_clearrow, r1
    jsr     @r1
    mov     #13, r4
    mov.l   =fn_clearrow, r1
    jsr     @r1
    mov     #12, r4

    mov.l   =stage_ptrs, r8     ; row 8 = first and last names
    mov.l   @r8, r4
    mov     #8, r5
    mov     #8, r6
    shll2   r6
    shll2   r6
    mov     #2, r7
    bsr     prop_draw8
    nop
    mov.l   @(4,r8), r4
    mov     #80, r5
    shll    r5                  ; x = 160
    mov     #8, r6
    shll2   r6
    shll2   r6
    mov     #2, r7
    bsr     prop_draw8
    nop

    mov.l   @(8,r8), r4         ; row 9 = codename
    mov     #8, r5
    mov     #9, r6
    shll2   r6
    shll2   r6
    mov     #2, r7
    bsr     prop_draw8
    nop

    mov.l   @(12,r8), r4        ; row 10 = city and ward
    mov     #8, r5
    mov     #10, r6
    shll2   r6
    shll2   r6
    mov     #2, r7
    bsr     prop_draw8
    nop
    mov.l   @(16,r8), r4
    mov     #80, r5
    shll    r5                  ; x = 160
    mov     #10, r6
    shll2   r6
    shll2   r6
    mov     #2, r7
    bsr     prop_draw8
    nop

    mov.l   =OCC_PROMPT, r4     ; row 13 = Occupation + selected value
    mov     #8, r5
    mov     #13, r6
    shll2   r6
    shll2   r6                  ; y = 208
    mov     #2, r7
    bsr     prop_draw
    nop
    mov.l   =g_occ, r2
    mov.b   @r2, r2
    extu.b  r2, r0
    shll2   r0
    shll    r0                  ; g_occ * 8
    mov.l   =OCC_INFO, r1
    add     r0, r1
    mov.l   @r1, r4             ; OCC_INFO[g_occ].ascii
    mov     #112, r5
    mov     #13, r6
    shll2   r6
    shll2   r6                  ; y = 208
    mov     #2, r7
    bsr     prop_draw
    nop

    mov.l   =CONFIRM_INFO, r8  ; row 12 = All OK? / centered YES / centered NO
    mov     #3, r9
co_label:
    mov.l   @r8, r4
    mov.w   @(4,r8), r0
    extu.w  r0, r5
    mov.w   @(6,r8), r0
    extu.w  r0, r6
    mov     #2, r7
    bsr     prop_draw
    nop
    add     #8, r8
    dt      r9
    bf      co_label
    mov.l   =fn_upload, r1
    jsr     @r1
    nop
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; ===== commit (type 12, once after the 17-frame fade) =======================
commit:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    sts.l   pr, @-r15
    mov     #0, r8              ; --- NAME_FW rows for the 5 fields
cm_field:
    mov.l   =stage_ptrs, r1
    mov     r8, r0
    shll2   r0
    mov.l   @(r0,r1), r9
    mov     #18, r1
    mov     r8, r0
    mulu.w  r1, r0
    mov.l   =NAME_FW, r10
    sts     macl, r0
    add     r0, r10
    mov     #0, r2              ; find length (trailing 0/space trimmed)
    mov     #0, r11
cm_scan:
    mov     r9, r1
    add     r2, r1
    mov.b   @r1, r1
    extu.b  r1, r0
    tst     r0, r0
    bt      cm_sk
    cmp/eq  #0x20, r0
    bt      cm_sk
    mov     r2, r11
    add     #1, r11
cm_sk:
    add     #1, r2
    mov     r2, r0
    cmp/eq  #8, r0
    bf      cm_scan
    mov     #0, r2
    tst     r11, r11
    bt      cm_term
cm_wr:
    mov     r9, r1
    add     r2, r1
    mov.b   @r1, r1
    extu.b  r1, r1
    tst     r1, r1
    bf      cm_wr2
    mov     #0x20, r1           ; interior blank -> space
cm_wr2:
    mov     r1, r0
    add     #-32, r0
    shll    r0
    mov.l   =ascii_to_atlas, r3
    mov.w   @(r0,r3), r1
    extu.w  r1, r1
    mov.w   r1, @r10
    add     #2, r10
    add     #1, r2
    cmp/eq  r11, r2
    bf      cm_wr
cm_term:
    mov.w   =0x8000, r1
    mov.w   r1, @r10
    add     #1, r8
    mov     r8, r0
    cmp/eq  #5, r0
    bf      cm_field
    mov.l   =stage_ptrs, r1     ; --- codename charmap bytes -> 0x23FFD0
    mov.l   @(8,r1), r9
    mov.l   =CODENAME, r10
    mov     #8, r8
cm_cn:
    mov.b   @r9+, r1
    extu.b  r1, r0
    tst     r0, r0
    bt/s    cm_cn2
    mov     #0, r1
    mov.l   =ascii_to_charmap, r2
    add     #-32, r0
    mov.b   @(r0,r2), r1
    extu.b  r1, r1
cm_cn2:
    mov.b   r1, @r10
    add     #1, r10
    dt      r8
    bf      cm_cn
    ; NAME_FW_FULL follows the authored full-name token order and separator.
    ; The default EN values preserve the mature First, space, Last byte layout.
    mov.l   =0x00008000, r3
    ; The two @FULL_NAME_*@ link tokens are rendered to NAME_FW/18 for the
    ; default order (preserving exact mature bytes), or to the reversed field
    ; address/0. They are source-level links, not hand-assembled opcodes.
    mov.l   =@FULL_NAME_FIRST@, r9
    mov.l   =NAME_FW_FULL, r10
cm_f1:
    mov.w   @r9+, r1
    extu.w  r1, r0
    cmp/eq  r3, r0
    bt      cm_f2
    mov.w   r1, @r10
    bra     cm_f1
    add     #2, r10
cm_f2:
    mov.w   =FULL_NAME_SEPARATOR, r1
    mov.w   r1, @r10
    add     #2, r10
    mov.l   =NAME_FW, r9
    add     #@FULL_NAME_SECOND_OFFSET@, r9
cm_f3:
    mov.w   @r9+, r1
    extu.w  r1, r0
    cmp/eq  r3, r0
    bt      cm_f4
    mov.w   r1, @r10
    bra     cm_f3
    add     #2, r10
cm_f4:
    mov.w   r1, @r10
    mov.l   =g_occ, r1          ; --- occupation flags (stock bits 33/34/35)
    mov.b   @r1, r1
    extu.b  r1, r0
    tst     #1, r0
    bt      cm_o34
    cmp/eq  #1, r0
    bt      cm_o33
    cmp/eq  #3, r0
    bt      cm_o35
    bra     cm_done
    nop
cm_o34:
    mov.l   =fn_setbit, r1
    jsr     @r1
    mov     #34, r4
    bra     cm_done
    nop
cm_o33:
    mov.l   =fn_setbit, r1
    jsr     @r1
    mov     #33, r4
    bra     cm_done
    nop
cm_o35:
    mov.l   =fn_setbit, r1
    jsr     @r1
    mov     #35, r4
cm_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; ===== prop_draw8(r4=fixed 8-byte ASCII, r5=x, r6=y, r7=color) =============
; Copies the bounded staging row into a terminated scratch string, then uses
; the same proportional renderer as static labels. Returns the final x in r0.
prop_draw8:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov.l   =prop_buffer, r1
    mov     #8, r2
pd8_copy:
    mov.b   @r8+, r0
    mov.b   r0, @r1
    add     #1, r1
    dt      r2
    bf      pd8_copy
    mov     #0, r0
    mov.b   r0, @r1
    mov.l   =prop_buffer, r4
    bsr     prop_draw
    nop
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

; ===== prop_draw(r4=ascii ptr, r5=x, r6=y, r7=color) -> r0 = end x =========
; Proportional FONT16 text onto the canvas via the stock per-pixel blitter
; 0x0602f510; advance per glyph from the measured width table. Draws until a 0
; byte. Preserves r8-r12 (so callers can loop).
prop_draw:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
pd_loop:
    mov.b   @r8+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      pd_end
    add     #-32, r0
    mov     r0, r12             ; index = ascii - 0x20
    mov.l   =ascii_to_atlas, r1
    shll    r0
    mov.w   @(r0,r1), r4        ; FONT16 code
    extu.w  r4, r4
    mov     r11, r0
    add     #1, r0
    mov.l   r0, @-r15           ; stack arg: shadow color = fg+1
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov.l   =fn_blit, r1
    jsr     @r1
    nop
    add     #4, r15
    mov.l   =ascii_to_width, r1
    mov     r12, r0
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    add     r0, r9              ; x += width
    bra     pd_loop
    nop
pd_end:
    mov     r9, r0
    lds.l   @r15+, pr
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; ===== tab_draw (proportional UPPER/lower/SYMBOL; replaces 0x06030780) =====
tab_draw:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =fn_clearrow, r1
    jsr     @r1
    mov     #11, r4             ; clear canvas row 11
    mov     #0, r8
tabd_loop:
    mov.l   =g_type, r1
    mov.b   @r1, r1
    extu.b  r1, r0
    mov     #6, r1
    cmp/hs  r1, r0              ; occupation/confirm/commit -> disabled
    bt      tabd_dis
    mov.l   =g_tab, r1
    mov.b   @r1, r1
    extu.b  r1, r0
    mov     r8, r1
    add     #7, r1              ; selected tab id = 7 + index
    cmp/eq  r1, r0
    bf      tabd_norm
    mov     #12, r7             ; selected (yellow)
    bra     tabd_go
    nop
tabd_norm:
    mov     #2, r7              ; normal (white)
    bra     tabd_go
    nop
tabd_dis:
    mov     #4, r7              ; disabled (gray)
tabd_go:
    mov.l   =TAB_INFO, r1
    mov     r8, r0
    shll2   r0
    shll    r0                  ; index * 8
    add     r0, r1
    mov.l   @r1, r4             ; ascii ptr
    mov.w   @(4,r1), r0
    extu.w  r0, r5              ; centered x
    mov     #88, r6
    shll    r6                  ; y = 176 (row 11)
    bsr     prop_draw
    nop
    add     #1, r8
    mov     r8, r0
    cmp/eq  #3, r0
    bf      tabd_loop
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool

; ===== occ_draw(r4=selected 0-5): proportional EN occupation grid + prompt ==
; selected label drawn yellow; row 13 gets the "Occupation" prompt. Replaces the
; stock grid drawer 0x06030b00 (via eh_to_occ) and reruns on cursor move.
occ_draw:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     r4, r9             ; selected choice
    mov.l   =fn_clear07, r1    ; clear canvas rows 0-7
    jsr     @r1
    nop
    mov     #0, r8
occd_loop:
    mov.l   =OCC_INFO, r1
    mov     r8, r0
    shll2   r0
    shll    r0                 ; index * 8
    add     r0, r1
    mov.l   @r1, r4            ; ascii ptr
    mov.w   @(4,r1), r0
    extu.w  r0, r5             ; x
    mov.w   @(6,r1), r0
    extu.w  r0, r6             ; y
    mov     #2, r7             ; white
    cmp/eq  r8, r9
    bf      occd_col
    mov     #12, r7            ; selected -> yellow
occd_col:
    bsr     prop_draw
    nop
    add     #1, r8
    mov     r8, r0
    cmp/eq  #6, r0
    bf      occd_loop
    mov.l   =fn_clearrow, r1   ; row 13 = "Occupation" prompt (proportional)
    jsr     @r1
    mov     #13, r4
    mov.l   =OCC_PROMPT, r4
    mov     #8, r5
    mov     #13, r6
    shll2   r6
    shll2   r6                 ; y = 208 (row 13)
    mov     #2, r7
    bsr     prop_draw
    nop
    mov.l   =fn_upload, r1     ; canvas rows 0-7 -> VDP1 (row 13 sprited separately)
    jsr     @r1
    nop
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool

; ===== occ_cursor: per-frame selection tracker (replaces box 0x0603049c) ====
; Runs from deco every frame while the occupation screen is up. choice =
; (row-1) + (col==4 ? 0 : 1); redraw (recolor) only when it changes.
occ_cursor:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =g_row, r1
    mov.w   @r1, r1
    extu.w  r1, r0
    add     #-1, r0            ; row-1 = 0/2/4
    mov     r0, r8
    mov.l   =g_col, r1
    mov.w   @r1, r1
    extu.w  r1, r0
    cmp/eq  #4, r0
    bt      occ_c0
    add     #1, r8             ; right column -> +1
occ_c0:
    mov.l   =occ_last, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    cmp/eq  r8, r0
    bt      occ_cdone          ; unchanged
    mov.l   =occ_last, r1
    mov.w   r8, @r1
    mov     r8, r4
    bsr     occ_draw
    nop
occ_cdone:
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool
occ_last:
    .word   0
    .align  4
prop_buffer:
    .byte   0
    .byte   0
    .byte   0
    .byte   0
    .byte   0
    .byte   0
    .byte   0
    .byte   0
    .byte   0
    .align  4
