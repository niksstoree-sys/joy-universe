-- =========================================
-- JOY UNIVERSE - Welcome & Leave System (Stage 2)
-- =========================================

CREATE TABLE IF NOT EXISTS welcome_config (
    guild_id            TEXT PRIMARY KEY,
    enabled             INTEGER NOT NULL DEFAULT 0,
    channel_id          TEXT,

    content             TEXT,                         -- pesan text biasa (opsional, tampil di atas embed/card)
    mention_user        INTEGER NOT NULL DEFAULT 0,    -- kalau 1, otomatis mention user di content

    embed_enabled       INTEGER NOT NULL DEFAULT 1,
    embed_title         TEXT DEFAULT 'Selamat Datang!',
    embed_description   TEXT DEFAULT '{user_mention} baru saja bergabung ke **{server}**!',
    embed_color         TEXT,                         -- hex, kalau NULL pakai default_color bot
    embed_footer_text   TEXT,
    embed_footer_icon   TEXT,
    embed_thumbnail     TEXT DEFAULT '{user_avatar}',
    embed_image         TEXT,                         -- banner besar, support variable
    embed_author_name   TEXT,
    embed_author_icon   TEXT,
    embed_timestamp     INTEGER NOT NULL DEFAULT 1,

    card_enabled        INTEGER NOT NULL DEFAULT 0,
    card_background     TEXT,                         -- URL background custom, kalau NULL pakai default
    card_avatar_position TEXT NOT NULL DEFAULT 'center', -- left | center | right
    card_text_position   TEXT NOT NULL DEFAULT 'bottom',  -- top | center | bottom

    button_label        TEXT,
    button_url          TEXT,

    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leave_config (
    guild_id            TEXT PRIMARY KEY,
    enabled             INTEGER NOT NULL DEFAULT 0,
    channel_id          TEXT,

    content             TEXT,
    mention_user        INTEGER NOT NULL DEFAULT 0,

    embed_enabled       INTEGER NOT NULL DEFAULT 1,
    embed_title         TEXT DEFAULT 'Sampai Jumpa!',
    embed_description   TEXT DEFAULT '**{user_tag}** telah meninggalkan **{server}**.',
    embed_color         TEXT,
    embed_footer_text   TEXT,
    embed_footer_icon   TEXT,
    embed_thumbnail     TEXT DEFAULT '{user_avatar}',
    embed_image         TEXT,
    embed_author_name   TEXT,
    embed_author_icon   TEXT,
    embed_timestamp     INTEGER NOT NULL DEFAULT 1,

    card_enabled        INTEGER NOT NULL DEFAULT 0,
    card_background     TEXT,
    card_avatar_position TEXT NOT NULL DEFAULT 'center',
    card_text_position   TEXT NOT NULL DEFAULT 'bottom',

    button_label        TEXT,
    button_url          TEXT,

    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
