from app.lyrics import search_lrclib


def test_search_lrclib_sorts_exact_well_formatted_match_first():
    def transport(url, **kwargs):
        assert "track_name=%E3%83%A9%E3%82%A4%E3%83%88%E3%83%80%E3%83%B3%E3%82%B9" in url
        assert "artist_name=%E3%82%B5%E3%82%AB%E3%83%8A%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3" in url
        assert kwargs["timeout"] == 15.0
        return [
            {
                "id": 1,
                "trackName": "ライトダンス",
                "artistName": "サカナクション",
                "albumName": "シンシロ",
                "duration": 342,
                "plainLyrics": "一行目 二行目\n三行目 四行目",
                "syncedLyrics": "[00:01.00]一行目 二行目",
            },
            {
                "id": 2,
                "trackName": "ライトダンス",
                "artistName": "サカナクション",
                "albumName": "魚図鑑",
                "duration": 212.4,
                "plainLyrics": "一行目\n二行目\n三行目\n四行目",
                "syncedLyrics": "[00:01.00]一行目\n[00:02.00]二行目",
            },
        ]

    results = search_lrclib("ライトダンス", "サカナクション", transport=transport)

    assert [item.id for item in results] == [2, 1]
    assert results[0].has_synced_lyrics is True


def test_search_lrclib_derives_plain_lyrics_and_skips_empty_items():
    def transport(*_, **__):
        return [
            {
                "id": 3,
                "trackName": "曲",
                "artistName": "歌手",
                "duration": 180,
                "plainLyrics": None,
                "syncedLyrics": "[00:01.00]最初の行\n[00:02.50]次の行\n[00:03.00]",
            },
            {"id": 4, "trackName": "空", "plainLyrics": None, "syncedLyrics": None},
        ]

    results = search_lrclib("曲", transport=transport)

    assert len(results) == 1
    assert results[0].plain_lyrics == "最初の行\n次の行"
