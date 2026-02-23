#!/usr/bin/env python3
"""
Test TMDB API integration with real file names from the media library.
This script tests the normalization and TMDB lookup functionality with actual files.
"""
from src.integrations.tmdb_client import TMDBClient
from src.utils.naming_normalizer import (
    normalize_movie_filename,
    normalize_tv_filename,
    create_movie_folder_name,
    create_tv_folder_name
)
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Real movie folder names from your library
MOVIE_TEST_CASES = [
    "13 Horas - Os Soldados Secretos de Benghazi 2016 [1080p] WWW.BLUDV.COM",
    "300  (1080p)WWW.BLUDV.COM",
    "300.A.Ascensao.Do.Imperio.2014.1080p.BRRip.x264.DualAudio.SpeedBR",
    "[ACESSE COMANDOTORRENTS.COM] Alita - Anjo de Combate 2019 [1080p] [BluRay] [DUAL]",
    "A.Chegada.2016.1080p.BluRay.5.1.x264.DUAL-Kraven",
    "A Escolha (2016) 5.1 CH Dublado 1080p (By-LuanHarper)",
    "A.Grande.Escolha.2014.1080p.Dual",
    "A Guerra do Amanhã 2021 WEB-DL 1080p DUAL 5.1",
    "A Origem (2010) 1080p 5.1 Dublado - Alan_680",
    "A Origem dos Guardioes",
    "Até o Último Homem 2017 (1080p)",
    "Atirador.2007.1080p.x264.WEB-DL.DUAL.5.1-SF",
    "Avatar EXTENDED 2009 BluRay 1080p DUAL 5.1",
    "Avatar - O Caminho da Água 2022 WEB-DL 1080p x264 DUAL 7.1",
    "Bailarina - Do Universo De John Wick 2025 WEB-DL 1080p x264 DUAL 5.1",
    "Bastardos Inglórios 2009 [1080p] WWW.BLUDV.COM",
    "Batman.Begins.2005.UHD.BluRay.2160p.DDP.5.1.DV.HDR.x265-hallowed.DUAL-wastaken",
    "Batman.Vs.Superman.A.Origem.da.Justica.2016.Versao.Estendida.1080p.BluRay.x264.SPARKS-DUAL-LAPUMiA",
    "Beekeeper-Rede.de.Vinganca.2024.1080p.WEB-DL.EAC3.AAC.DUAL.5.1",
    "Black.Panther.Wakanda.Forever.2022.2160p.IMAX.DSNP.WEB-DL.DDP5.1.Atmos.DV.H265.DUAL-andrehsa",
    "Capitão América O Primeiro Vingador",
    "Captain.America.Civil.War.2016.2160p.IMAX.DSNP.WEB-DL.DDP5.1.Atmos.DV.H265.DUAL-andrehsa",
    "Captain.America.The.Winter.Soldier.2014.2160p.DSNP.WEB-DL.DDP5.1.Atmos.DV.H265.DUAL-andrehsa",
    "Carros 1 (2006) 1080p Dublado JohnL",
    "Carros 2",
    "Carros 3 2017 [BluRay] (1080p) WWW.BLUDV.COM",
    "Círculo de Fogo (2013) BDRip 1080p Dublado - The Pirate Filmes",
]

# Real TV show folder names from your library
TV_TEST_CASES = [
    "Chernobyl.S01.1080p.WEB-DL.DD5.1.H264-DUAL-RK",
    "Irmaos.de.Guerra.2001.S01.BRRip.1080p.AVC-AXS.DUAL-VET",
    "The.Pitt.S01.2160p.HMAX.WEB-DL.DDP5.1.DV.HDR.H.265-Dual.RvT",
]

# Real anime folder names from your library
ANIME_TEST_CASES = [
    "Demon.Slayer.Kimetsu.no.Yaiba.Entertainment.District.Arc.S03.2160p.B-Global.WEB-DL.AAC2.0.H.264.DUAL-OLYMPUS",
    "Demon.Slayer.Kimetsu.no.Yaiba.S01.2160p.B-Global.WEB-DL.AAC2.0.H.264.DUAL-OLYMPUS",
    "Demon.Slayer.Kimetsu.no.Yaiba.S05.1080p.CR.WEB-DL.AAC2.0.H.264.DUAL-lucano22",
    "Demon.Slayer.S02.1080p.BluRay.FLAC2.0.H.264.DUAL-Eternal",
    "Demon.Slayer.S04.1080p.BluRay.FLAC2.0.H.264.DUAL-Anitsu",
    "Solo.Leveling.S01.2160p.B-Global.WEB-DL.AAC2.0.H.264.DUAL-Anitsu",
    "Solo.Leveling.S02.1080p.CR.WEB-DL.AAC2.0.H.264-DUAL-S74Ll10n",
]


def test_movie_normalization():
    """Test movie filename normalization with real examples"""
    print("\n" + "=" * 80)
    print(" MOVIE NORMALIZATION TEST")
    print("=" * 80)

    results = []
    for folder_name in MOVIE_TEST_CASES:
        title, year = normalize_movie_filename(folder_name)
        results.append({
            'original': folder_name,
            'title': title,
            'year': year
        })

        print(f"\n📁 Original: {folder_name}")
        print(f"   ➜ Title: {title}")
        print(f"   ➜ Year: {year}")

    return results


def test_tv_normalization():
    """Test TV filename normalization with real examples"""
    print("\n" + "=" * 80)
    print(" TV SHOW NORMALIZATION TEST")
    print("=" * 80)

    results = []
    for folder_name in TV_TEST_CASES:
        title, season, episode, year = normalize_tv_filename(folder_name)
        results.append({
            'original': folder_name,
            'title': title,
            'season': season,
            'episode': episode,
            'year': year
        })

        print(f"\n📁 Original: {folder_name}")
        print(f"   ➜ Title: {title}")
        print(f"   ➜ Season: {season}, Episode: {episode}")
        print(f"   ➜ Year: {year}")

    return results


def test_anime_normalization():
    """Test anime filename normalization with real examples"""
    print("\n" + "=" * 80)
    print(" ANIME NORMALIZATION TEST")
    print("=" * 80)

    results = []
    for folder_name in ANIME_TEST_CASES:
        title, season, episode, year = normalize_tv_filename(folder_name)
        results.append({
            'original': folder_name,
            'title': title,
            'season': season,
            'episode': episode,
            'year': year
        })

        print(f"\n📁 Original: {folder_name}")
        print(f"   ➜ Title: {title}")
        print(f"   ➜ Season: {season}, Episode: {episode}")
        print(f"   ➜ Year: {year}")

    return results


async def test_tmdb_movie_lookup(movie_results: list):
    """Test TMDB API lookup for movies"""
    print("\n" + "=" * 80)
    print(" TMDB MOVIE LOOKUP TEST")
    print("=" * 80)

    api_key = os.getenv("TMDB_API_KEY", "")
    if not api_key:
        print("\n⚠️  TMDB_API_KEY not set. Skipping API tests.")
        return

    async with TMDBClient(api_key=api_key) as client:
        for item in movie_results[:15]:  # Test first 15 to avoid rate limits
            title = item['title']
            year = item['year']

            print(f"\n🔍 Searching: '{title}' ({year})")

            result = await client.search_movie(title=title, year=year)

            if result.success:
                data = result.data
                tmdb_id = data.get('id')
                tmdb_title = data.get('title')
                tmdb_year = data.get('release_date', '')[:4]
                popularity = data.get('popularity', 0)

                # Generate folder name
                folder_name = create_movie_folder_name(
                    tmdb_title, int(tmdb_year) if tmdb_year else year, tmdb_id)

                print(f"   ✅ Found: {tmdb_title} ({tmdb_year})")
                print(
                    f"      TMDB ID: {tmdb_id} | Popularity: {popularity:.1f}")
                print(f"      📂 Folder: {folder_name}")
            else:
                print(f"   ❌ Not found: {result.error}")

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)


async def test_tmdb_tv_lookup(tv_results: list):
    """Test TMDB API lookup for TV shows"""
    print("\n" + "=" * 80)
    print(" TMDB TV SHOW LOOKUP TEST")
    print("=" * 80)

    api_key = os.getenv("TMDB_API_KEY", "")
    if not api_key:
        print("\n⚠️  TMDB_API_KEY not set. Skipping API tests.")
        return

    async with TMDBClient(api_key=api_key) as client:
        for item in tv_results:
            title = item['title']
            year = item['year']

            print(f"\n🔍 Searching: '{title}' ({year})")

            result = await client.search_tv_show(title=title, year=year)

            if result.success:
                data = result.data
                tmdb_id = data.get('id')
                tmdb_title = data.get('name')
                tmdb_year = data.get('first_air_date', '')[:4]
                popularity = data.get('popularity', 0)

                # Generate folder name
                folder_name = create_tv_folder_name(tmdb_title, int(
                    tmdb_year) if tmdb_year else year, tmdb_id)

                print(f"   ✅ Found: {tmdb_title} ({tmdb_year})")
                print(
                    f"      TMDB ID: {tmdb_id} | Popularity: {popularity:.1f}")
                print(f"      📂 Folder: {folder_name}")
            else:
                print(f"   ❌ Not found: {result.error}")

            await asyncio.sleep(0.3)


async def test_tmdb_anime_lookup(anime_results: list):
    """Test TMDB API lookup for anime"""
    print("\n" + "=" * 80)
    print(" TMDB ANIME LOOKUP TEST")
    print("=" * 80)

    api_key = os.getenv("TMDB_API_KEY", "")
    if not api_key:
        print("\n⚠️  TMDB_API_KEY not set. Skipping API tests.")
        return

    async with TMDBClient(api_key=api_key) as client:
        for item in anime_results:
            title = item['title']
            year = item['year']

            print(f"\n🔍 Searching: '{title}' ({year})")

            result = await client.search_tv_show(title=title, year=year, media_subtype="anime")

            if result.success:
                data = result.data
                tmdb_id = data.get('id')
                tmdb_title = data.get('name')
                tmdb_year = data.get('first_air_date', '')[:4]
                popularity = data.get('popularity', 0)

                # Generate folder name
                folder_name = create_tv_folder_name(tmdb_title, int(
                    tmdb_year) if tmdb_year else year, tmdb_id)

                print(f"   ✅ Found: {tmdb_title} ({tmdb_year})")
                print(
                    f"      TMDB ID: {tmdb_id} | Popularity: {popularity:.1f}")
                print(f"      📂 Folder: {folder_name}")
            else:
                print(f"   ❌ Not found: {result.error}")

            await asyncio.sleep(0.3)


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print(" TMDB INTEGRATION TEST - REAL FILES")
    print(" Testing with actual file names from media library")
    print("=" * 80)

    # Step 1: Test normalization
    movie_results = test_movie_normalization()
    tv_results = test_tv_normalization()
    anime_results = test_anime_normalization()

    # Step 2: Test TMDB API lookup
    await test_tmdb_movie_lookup(movie_results)
    await test_tmdb_tv_lookup(tv_results)
    await test_tmdb_anime_lookup(anime_results)

    print("\n" + "=" * 80)
    print(" TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    # Load .env file if exists
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded .env from {env_path}")

    asyncio.run(main())
