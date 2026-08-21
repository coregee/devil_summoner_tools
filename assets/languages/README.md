# Language projects

Language project files describe localization-specific character needs and font
overrides. English is the built-in base because the canonical `translation`
fields currently contain the English translation.

Additional projects inherit the base font definitions. Their `characters`
field lists extra language-specific characters, while `fonts` records imported
typefaces and the glyph-slot mappings chosen for individual Saturn fonts.

The translation editor creates and updates these files. Imported typefaces are
stored under `assets/font/imported/<language>/`; users are responsible for
ensuring that the typeface license permits use and redistribution.

