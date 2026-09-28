# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
sleep_norms.py — Einheitliche Normbereiche für Schlafstadien (Tiefschlaf, REM)

@tier        infrastructure
@purpose.de  Stellt EINEN gemeinsamen, zitierten Satz Normbereiche für Tiefschlaf-
             (N3) und REM-Anteil an der Gesamtschlafzeit bereit, den alle
             Analyse-Skripte verwenden, statt jeweils eigene (und widersprüchliche)
             Werte zu pflegen.
@purpose.en  Provides ONE shared, cited set of norm ranges for deep-sleep (N3) and
             REM percentage of total sleep time, used by all analysis scripts
             instead of each maintaining its own (and contradictory) values.
@method.de   Reine Konstanten, keine Berechnung. Vor dieser Zusammenführung
             verwendete analyse_sleep_stages.py 13–18 % (Tiefschlaf) / 18–23 %
             (REM), analyse_sleep_respiration.py dagegen 15–25 % / 20–25 % für
             denselben Sachverhalt — zwei Bewertungen desselben Befunds. Die hier
             festgelegten Bereiche (Tiefschlaf 13–23 %, REM 18–25 %) sind so
             gewählt, dass der empirische Populationsmittelwert aus der bislang
             größten PSG-Metaanalyse gesunder volljähriger Personen (Boulos et al. 2019,
             n=5273: Tiefschlaf 20,4 %, 95%-CI 19,0–21,8 %; REM 19,0 %, 95%-CI
             18,5–19,6 %) innerhalb des Bereichs liegt — insbesondere die REM-
             Untergrenze wurde deshalb bewusst auf 18 % (statt der in älteren
             Lehrbuchangaben kursierenden 20 %) gesetzt: ein Normbereich, der den
             empirisch gemessenen Populationsmittelwert selbst ausschließt, ist
             per Definition falsch kalibriert.
@method.en   Pure constants, no computation. Before this consolidation,
             analyse_sleep_stages.py used 13-18% (deep) / 18-23% (REM), while
             analyse_sleep_respiration.py used 15-25% / 20-25% for the same fact
             — two assessments of the same finding. The ranges fixed here (deep
             13-23%, REM 18-25%) are chosen so the empirical population mean from
             the largest published PSG meta-analysis of healthy adults to date
             (Boulos et al. 2019, n=5273: deep 20.4%, 95% CI 19.0-21.8%; REM
             19.0%, 95% CI 18.5-19.6%) falls inside the range — the REM lower
             bound in particular was deliberately set to 18% (rather than the
             20% figure circulating in older textbook summaries): a "normal
             range" that excludes the empirically measured population mean is by
             definition miscalibrated.
@relevance.de  Tiefschlaf- und REM-Anteil sind etablierte Marker für Schlafqualität
               und -architektur; ein einheitlicher, zitierter Normbereich verhindert,
               dass derselbe gemessene Wert je nach Skript unterschiedlich (und
               teils widersprüchlich) bewertet wird.
@relevance.en  Deep-sleep and REM percentage are established markers of sleep
               quality and architecture; one shared, cited norm range prevents the
               same measured value from being assessed differently (and
               sometimes contradictorily) depending on which script reports it.
@reads       keine
@writes      keine
@refs        Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019).
             Normal polysomnography parameters in healthy adults: a systematic
             review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543.
             doi:10.1016/S2213-2600(19)30057-8
             (Tabelle 2 der Publikation: Tiefschlaf/N3 20,4 % [95%-CI 19,0-21,8 %],
             REM 19,0 % [95%-CI 18,5-19,6 %], Gesamtstichprobe n=5273 gesunde
             volljährige Personen, 108-158 gepoolte Kontrollgruppen je Parameter.)
@limits.de   Boulos et al. 2019 berichtet die 95%-CI des gepoolten Populations-
             MITTELWERTS über Studien hinweg, nicht die Streuung zwischen
             Individuen/Nächten — als individuelles Prognoseintervall wäre dieser
             CI-Bereich zu eng. Die hier definierten Bereiche sind deshalb bewusst
             breiter als die CI und dienen dem Vergleich eines über mehrere Nächte
             gemittelten persönlichen Werts gegen den Populationsschnitt, nicht der
             Bewertung einer einzelnen Nacht. Wearable-Schlafstaging (Apple Watch,
             Oura) hat zudem geringere Genauigkeit als die PSG, auf der Boulos et
             al. 2019 basiert.
@limits.en   Boulos et al. 2019 reports the 95% CI of the pooled population MEAN
             across studies, not the spread between individuals/nights — as an
             individual prediction interval this CI would be too narrow. The
             ranges defined here are therefore deliberately wider than the CI and
             are meant for comparing a personal value averaged over multiple
             nights against the population mean, not for judging a single night.
             Wearable sleep staging (Apple Watch, Oura) also has lower accuracy
             than the PSG that Boulos et al. 2019 is based on.
@usage
    from modules.sleep_norms import (
        DEEP_NORM_MIN, DEEP_NORM_MAX, REM_NORM_MIN, REM_NORM_MAX,
    )
"""

# Tiefschlaf/N3-Anteil an der Gesamtschlafzeit (Prozent) — siehe @method/@refs oben.
DEEP_NORM_MIN, DEEP_NORM_MAX = 13.0, 23.0

# REM-Anteil an der Gesamtschlafzeit (Prozent) — siehe @method/@refs oben.
REM_NORM_MIN, REM_NORM_MAX = 18.0, 25.0
