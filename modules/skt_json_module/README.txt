Storm King's Thunder JSON conversion
Generated: 2026-07-03T20:15:03

Recommended usage with your dm.py:
  python3 dm.py --session sessions/skt.json --module skt_module_index.json --characters characters/party.json

For active play, load one chapter file instead of the full index, for example:
  python3 dm.py --session sessions/skt.json --module chapter_1_a_great_upheaval.json --characters characters/party.json

Files:
- skt_module_index.json: compact TOC/index for the whole adventure.
- One JSON file per top-level chapter/appendix with extracted section text.

