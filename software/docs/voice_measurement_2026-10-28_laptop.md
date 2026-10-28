# Voice measurement, 2026-10-28 (Jordan's laptop)

AlfieBot 0.13.0 on Windows (i5-1135G7, CPU only), speech model
`vosk-model-small-en-us-0.15`, Piper voice `en_GB-cori-medium` (piper-tts
1.8.0). Synthetic voice only: no recordings of a child were made or used.

## `tools/measure_voice.py` (0.13.0)

16 words built from letters that sound alike, at speeds 0.85, 1.0 and 1.2,
with no background noise.

| | One letter at a time | Letters in a run |
|---|---|---|
| Right first time, no need to ask | 0 of 48 | 0 of 48 |
| AlfieBot would ask about a letter | 48 of 48 | 48 of 48 |
| Wrong but sure (the risky case) | 0 | 0 |
| Letters heard right | 84/162 (52%) | 49/162 (30%) |
| Time per word | 5.7 s | 5.0 s |

Wake word: "Hey AlfieBot" heard 5 of 6 times; woke by mistake for 1 of 15
other sentences. "alfie" is in the speech model's vocabulary ("alfiebot"
isn't, which is fine: the wake phrases are "alfie bot").

## Why letters were misheard

Checked letter by letter on the laptop:

1. **The voice, not the recogniser, was the main problem.** `letter_sound`
   sent "ay" for A, which the voice says as "eye". F, L, M, N, S, X and Z
   said on their own came out as 1 to 4.5 seconds of babble, heard as
   whole sentences ("path of lover" for S). espeak's phonemes for the
   letters are correct; the voice model itself can't say a lone short
   syllable like "em". Feeding phonemes directly, turning the randomness
   down, or picking the best of several takes did not help.
2. **"Letter, X." works.** With a comma, the voice pauses after "Letter",
   and cutting at the longest pause leaves a clean 0.34 to 0.56 s letter.
   23 of 26 letters were then heard right. F had no pause (0.13.1 then
   tries "Letter... F." and "Eff"), V still rambles (0.13.1 tries "Vee"),
   and R is a recognition problem (below). 0.13.1 makes letters this way,
   both when AlfieBot spells to the child and in `measure_voice.py`.
3. **R** (British "ah") was always heard as "oh". 0.13.1 adds "ah" as an R
   name and asks "R for rabbit or O for orange?" when unsure.
4. "aitch", "haitch", "x-ray", "xray" and "backspace" aren't in the small
   model's vocabulary; 0.13.1 leaves them out of the grammar.

## Still open

- **Confidence.** With the spelling grammar, the speech model's confidence
  for a correctly heard synthetic letter is usually 0.25 to 0.5, below
  `speech.min_confidence` (0.75), so AlfieBot would ask about almost every
  letter. That was measured with a synthetic voice only. Before changing
  the threshold, run the Letter test (Pairs and All sets) with real adult
  voices and look at the confidence of the letters heard right and wrong.
- Rerun `tools/measure_voice.py` with 0.13.1 to see the effect of the
  clean letters.
- A bigger speech model or whisper is only worth trying if Vosk is still
  poor with clean letters and real adult voices, and only after Jordan
  agrees to the download.
