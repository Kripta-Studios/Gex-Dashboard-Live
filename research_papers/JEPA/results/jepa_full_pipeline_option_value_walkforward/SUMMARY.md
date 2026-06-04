# OptionValueJEPA Walk-Forward Since 2022

Candidate labels: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\results\jepa_full_pipeline_option_policy\candidate_labels.parquet`
Train start: `20220801`
Min train months: `12`
Epochs per fold: `8`
Dynamic target: `future_best`
Exit margin: `-0.3`

## Overall Walk-Forward Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 3846 | 70.1% | 4.573 | +1,891,655 | -11,064 | +492 | 125.3 | 0.706 |
| fixed_delta_0.70_learned_exit_5m | 3846 | 70.9% | 4.444 | +1,755,495 | -11,374 | +456 | 117.6 | 0.706 |
| option_value_hold180_select_hard | 3846 | 60.0% | 3.456 | +1,929,069 | -12,999 | +502 | 116.9 | 0.573 |
| option_value_rule_select_hard | 3846 | 61.2% | 3.563 | +1,943,341 | -13,908 | +505 | 117.7 | 0.588 |
| option_value_best_select_hard | 3846 | 47.5% | 2.483 | +1,751,374 | -20,783 | +455 | 105.3 | 0.418 |
| option_value_best_select_learned_exit_5m | 3846 | 48.0% | 2.464 | +1,706,677 | -17,989 | +444 | 100.2 | 0.418 |
| oracle_best_delta_hard | 3846 | 70.5% | 11.120 | +3,893,656 | -7,507 | +1,012 | 114.5 | 0.526 |
| oracle_best_delta_oracle_exit | 3846 | 94.1% | 437.533 | +8,817,798 | -791 | +2,293 | 85.5 | 0.395 |

## Fold Metrics

| Month | Policy | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202308 | fixed_delta_0.70_hard | 125 | 73.6% | 6.245 | +61,160 | -1,612 |
| 202308 | fixed_delta_0.70_learned_exit_5m | 125 | 73.6% | 6.250 | +61,220 | -1,612 |
| 202308 | option_value_hold180_select_hard | 125 | 70.4% | 5.278 | +70,543 | -1,612 |
| 202308 | option_value_rule_select_hard | 125 | 69.6% | 4.995 | +67,998 | -2,267 |
| 202308 | option_value_best_select_hard | 125 | 56.8% | 2.992 | +58,894 | -3,238 |
| 202308 | option_value_best_select_learned_exit_5m | 125 | 56.8% | 3.060 | +60,888 | -3,065 |
| 202308 | oracle_best_delta_hard | 125 | 73.6% | 12.610 | +121,728 | -1,542 |
| 202308 | oracle_best_delta_oracle_exit | 125 | 96.0% | 348.227 | +228,961 | -410 |
| 202309 | fixed_delta_0.70_hard | 113 | 65.5% | 3.368 | +37,975 | -1,748 |
| 202309 | fixed_delta_0.70_learned_exit_5m | 113 | 65.5% | 3.367 | +37,956 | -1,748 |
| 202309 | option_value_hold180_select_hard | 113 | 55.8% | 2.996 | +46,599 | -2,548 |
| 202309 | option_value_rule_select_hard | 113 | 56.6% | 2.931 | +45,701 | -2,548 |
| 202309 | option_value_best_select_hard | 113 | 38.1% | 1.771 | +30,820 | -5,467 |
| 202309 | option_value_best_select_learned_exit_5m | 113 | 39.8% | 1.842 | +32,975 | -6,621 |
| 202309 | oracle_best_delta_hard | 113 | 65.5% | 8.026 | +89,507 | -1,356 |
| 202309 | oracle_best_delta_oracle_exit | 113 | 90.3% | 184.092 | +191,728 | -216 |
| 202310 | fixed_delta_0.70_hard | 112 | 73.2% | 6.343 | +67,877 | -1,343 |
| 202310 | fixed_delta_0.70_learned_exit_5m | 112 | 75.9% | 6.729 | +67,010 | -1,343 |
| 202310 | option_value_hold180_select_hard | 112 | 65.2% | 5.190 | +74,852 | -2,714 |
| 202310 | option_value_rule_select_hard | 112 | 65.2% | 4.789 | +70,722 | -3,660 |
| 202310 | option_value_best_select_hard | 112 | 51.8% | 3.116 | +65,607 | -3,642 |
| 202310 | option_value_best_select_learned_exit_5m | 112 | 54.5% | 3.303 | +69,078 | -3,642 |
| 202310 | oracle_best_delta_hard | 112 | 74.1% | 13.618 | +120,594 | -654 |
| 202310 | oracle_best_delta_oracle_exit | 112 | 94.6% | 1247.463 | +246,719 | -116 |
| 202311 | fixed_delta_0.70_hard | 117 | 70.1% | 3.897 | +42,189 | -2,456 |
| 202311 | fixed_delta_0.70_learned_exit_5m | 117 | 71.8% | 3.868 | +38,306 | -2,456 |
| 202311 | option_value_hold180_select_hard | 117 | 59.0% | 2.625 | +32,810 | -3,543 |
| 202311 | option_value_rule_select_hard | 117 | 59.0% | 2.659 | +32,985 | -3,543 |
| 202311 | option_value_best_select_hard | 117 | 45.3% | 1.906 | +29,151 | -4,894 |
| 202311 | option_value_best_select_learned_exit_5m | 117 | 47.9% | 1.772 | +23,792 | -4,894 |
| 202311 | oracle_best_delta_hard | 117 | 70.1% | 9.781 | +115,533 | -1,929 |
| 202311 | oracle_best_delta_oracle_exit | 117 | 88.9% | 202.421 | +227,954 | -295 |
| 202312 | fixed_delta_0.70_hard | 108 | 81.5% | 11.434 | +58,365 | -771 |
| 202312 | fixed_delta_0.70_learned_exit_5m | 108 | 81.5% | 12.277 | +63,081 | -771 |
| 202312 | option_value_hold180_select_hard | 108 | 67.6% | 4.409 | +52,230 | -2,227 |
| 202312 | option_value_rule_select_hard | 108 | 70.4% | 4.619 | +52,424 | -2,227 |
| 202312 | option_value_best_select_hard | 108 | 54.6% | 2.858 | +49,087 | -2,981 |
| 202312 | option_value_best_select_learned_exit_5m | 108 | 54.6% | 2.985 | +52,976 | -2,981 |
| 202312 | oracle_best_delta_hard | 108 | 82.4% | 26.835 | +127,408 | -688 |
| 202312 | oracle_best_delta_oracle_exit | 108 | 99.1% | 8479.660 | +512,368 | -60 |
| 202401 | fixed_delta_0.70_hard | 120 | 71.7% | 4.974 | +61,374 | -1,597 |
| 202401 | fixed_delta_0.70_learned_exit_5m | 120 | 72.5% | 4.816 | +56,599 | -1,597 |
| 202401 | option_value_hold180_select_hard | 120 | 63.3% | 4.500 | +72,577 | -2,403 |
| 202401 | option_value_rule_select_hard | 120 | 66.7% | 4.996 | +71,918 | -1,798 |
| 202401 | option_value_best_select_hard | 120 | 52.5% | 3.309 | +71,834 | -3,890 |
| 202401 | option_value_best_select_learned_exit_5m | 120 | 52.5% | 3.370 | +72,121 | -3,870 |
| 202401 | oracle_best_delta_hard | 120 | 72.5% | 11.988 | +144,647 | -1,296 |
| 202401 | oracle_best_delta_oracle_exit | 120 | 97.5% | 894.951 | +297,244 | -265 |
| 202402 | fixed_delta_0.70_hard | 111 | 71.2% | 4.959 | +53,205 | -2,516 |
| 202402 | fixed_delta_0.70_learned_exit_5m | 111 | 73.0% | 4.824 | +51,327 | -2,516 |
| 202402 | option_value_hold180_select_hard | 111 | 63.1% | 3.883 | +58,990 | -2,396 |
| 202402 | option_value_rule_select_hard | 111 | 64.0% | 4.128 | +59,569 | -2,396 |
| 202402 | option_value_best_select_hard | 111 | 41.4% | 2.253 | +47,621 | -4,766 |
| 202402 | option_value_best_select_learned_exit_5m | 111 | 41.4% | 2.205 | +46,605 | -4,852 |
| 202402 | oracle_best_delta_hard | 111 | 71.2% | 12.373 | +120,918 | -1,247 |
| 202402 | oracle_best_delta_oracle_exit | 111 | 92.8% | 295.516 | +236,745 | -190 |
| 202403 | fixed_delta_0.70_hard | 114 | 70.2% | 3.291 | +38,266 | -1,917 |
| 202403 | fixed_delta_0.70_learned_exit_5m | 114 | 71.1% | 3.178 | +35,046 | -1,896 |
| 202403 | option_value_hold180_select_hard | 114 | 62.3% | 2.686 | +37,494 | -2,747 |
| 202403 | option_value_rule_select_hard | 114 | 62.3% | 2.788 | +38,402 | -2,827 |
| 202403 | option_value_best_select_hard | 114 | 43.9% | 1.792 | +28,667 | -3,438 |
| 202403 | option_value_best_select_learned_exit_5m | 114 | 43.9% | 1.510 | +18,191 | -5,090 |
| 202403 | oracle_best_delta_hard | 114 | 70.2% | 7.958 | +99,558 | -1,503 |
| 202403 | oracle_best_delta_oracle_exit | 114 | 94.7% | 544.825 | +249,823 | -180 |
| 202404 | fixed_delta_0.70_hard | 126 | 72.2% | 7.749 | +82,069 | -2,970 |
| 202404 | fixed_delta_0.70_learned_exit_5m | 126 | 73.0% | 6.563 | +66,640 | -2,970 |
| 202404 | option_value_hold180_select_hard | 126 | 57.9% | 4.640 | +80,609 | -2,775 |
| 202404 | option_value_rule_select_hard | 126 | 57.9% | 4.553 | +78,271 | -2,775 |
| 202404 | option_value_best_select_hard | 126 | 41.3% | 2.610 | +67,331 | -4,475 |
| 202404 | option_value_best_select_learned_exit_5m | 126 | 42.1% | 2.619 | +67,415 | -4,475 |
| 202404 | oracle_best_delta_hard | 126 | 72.2% | 16.996 | +157,197 | -1,787 |
| 202404 | oracle_best_delta_oracle_exit | 126 | 97.6% | 7607.870 | +444,586 | -26 |
| 202405 | fixed_delta_0.70_hard | 122 | 68.0% | 3.979 | +48,976 | -2,726 |
| 202405 | fixed_delta_0.70_learned_exit_5m | 122 | 70.5% | 3.607 | +42,344 | -2,726 |
| 202405 | option_value_hold180_select_hard | 122 | 58.2% | 3.420 | +56,156 | -2,726 |
| 202405 | option_value_rule_select_hard | 122 | 61.5% | 3.483 | +56,393 | -2,726 |
| 202405 | option_value_best_select_hard | 122 | 42.6% | 1.803 | +33,076 | -4,529 |
| 202405 | option_value_best_select_learned_exit_5m | 122 | 44.3% | 1.735 | +28,867 | -5,382 |
| 202405 | oracle_best_delta_hard | 122 | 68.0% | 9.384 | +104,064 | -1,082 |
| 202405 | oracle_best_delta_oracle_exit | 122 | 91.8% | 507.904 | +362,539 | -179 |
| 202406 | fixed_delta_0.70_hard | 111 | 70.3% | 3.730 | +39,930 | -1,808 |
| 202406 | fixed_delta_0.70_learned_exit_5m | 111 | 70.3% | 3.857 | +41,785 | -1,808 |
| 202406 | option_value_hold180_select_hard | 111 | 64.0% | 3.145 | +43,934 | -2,927 |
| 202406 | option_value_rule_select_hard | 111 | 64.9% | 3.234 | +42,859 | -2,739 |
| 202406 | option_value_best_select_hard | 111 | 46.8% | 2.229 | +38,895 | -4,745 |
| 202406 | option_value_best_select_learned_exit_5m | 111 | 45.9% | 2.140 | +37,169 | -4,745 |
| 202406 | oracle_best_delta_hard | 111 | 70.3% | 7.794 | +79,246 | -1,409 |
| 202406 | oracle_best_delta_oracle_exit | 111 | 97.3% | 1006.703 | +225,086 | -128 |
| 202407 | fixed_delta_0.70_hard | 123 | 68.3% | 3.968 | +49,573 | -2,488 |
| 202407 | fixed_delta_0.70_learned_exit_5m | 123 | 69.9% | 4.182 | +50,800 | -2,690 |
| 202407 | option_value_hold180_select_hard | 123 | 56.1% | 2.666 | +42,250 | -3,897 |
| 202407 | option_value_rule_select_hard | 123 | 56.1% | 2.666 | +42,325 | -3,895 |
| 202407 | option_value_best_select_hard | 123 | 46.3% | 2.252 | +46,388 | -6,503 |
| 202407 | option_value_best_select_learned_exit_5m | 123 | 45.5% | 1.952 | +35,950 | -6,503 |
| 202407 | oracle_best_delta_hard | 123 | 69.1% | 10.444 | +117,407 | -1,626 |
| 202407 | oracle_best_delta_oracle_exit | 123 | 91.1% | 277.447 | +253,583 | -159 |
| 202408 | fixed_delta_0.70_hard | 125 | 69.6% | 4.390 | +58,091 | -3,343 |
| 202408 | fixed_delta_0.70_learned_exit_5m | 125 | 70.4% | 3.600 | +43,683 | -2,540 |
| 202408 | option_value_hold180_select_hard | 125 | 53.6% | 2.208 | +40,125 | -6,244 |
| 202408 | option_value_rule_select_hard | 125 | 56.8% | 2.535 | +44,475 | -6,244 |
| 202408 | option_value_best_select_hard | 125 | 45.6% | 1.925 | +39,695 | -5,758 |
| 202408 | option_value_best_select_learned_exit_5m | 125 | 45.6% | 1.784 | +33,705 | -5,758 |
| 202408 | oracle_best_delta_hard | 125 | 70.4% | 10.507 | +107,441 | -966 |
| 202408 | oracle_best_delta_oracle_exit | 125 | 92.8% | 391.800 | +259,990 | -140 |
| 202409 | fixed_delta_0.70_hard | 108 | 74.1% | 5.808 | +53,930 | -1,625 |
| 202409 | fixed_delta_0.70_learned_exit_5m | 108 | 73.1% | 5.197 | +47,200 | -1,625 |
| 202409 | option_value_hold180_select_hard | 108 | 57.4% | 3.283 | +49,635 | -2,670 |
| 202409 | option_value_rule_select_hard | 108 | 59.3% | 3.275 | +46,971 | -2,746 |
| 202409 | option_value_best_select_hard | 108 | 39.8% | 2.086 | +38,317 | -5,881 |
| 202409 | option_value_best_select_learned_exit_5m | 108 | 38.9% | 1.825 | +29,050 | -6,577 |
| 202409 | oracle_best_delta_hard | 108 | 74.1% | 13.405 | +95,945 | -804 |
| 202409 | oracle_best_delta_oracle_exit | 108 | 94.4% | 555.708 | +236,267 | -178 |
| 202410 | fixed_delta_0.70_hard | 120 | 80.0% | 6.777 | +58,863 | -1,913 |
| 202410 | fixed_delta_0.70_learned_exit_5m | 120 | 80.0% | 6.445 | +55,485 | -1,913 |
| 202410 | option_value_hold180_select_hard | 120 | 63.3% | 4.031 | +61,266 | -1,921 |
| 202410 | option_value_rule_select_hard | 120 | 66.7% | 4.605 | +68,293 | -2,070 |
| 202410 | option_value_best_select_hard | 120 | 54.2% | 3.060 | +59,115 | -3,274 |
| 202410 | option_value_best_select_learned_exit_5m | 120 | 53.3% | 3.281 | +66,194 | -3,274 |
| 202410 | oracle_best_delta_hard | 120 | 80.0% | 16.213 | +120,805 | -1,109 |
| 202410 | oracle_best_delta_oracle_exit | 120 | 95.8% | 291.279 | +227,784 | -291 |
| 202411 | fixed_delta_0.70_hard | 108 | 63.0% | 2.770 | +30,230 | -2,096 |
| 202411 | fixed_delta_0.70_learned_exit_5m | 108 | 64.8% | 3.085 | +34,717 | -2,096 |
| 202411 | option_value_hold180_select_hard | 108 | 51.9% | 2.626 | +36,261 | -2,624 |
| 202411 | option_value_rule_select_hard | 108 | 57.4% | 2.675 | +36,085 | -2,644 |
| 202411 | option_value_best_select_hard | 108 | 46.3% | 2.170 | +35,523 | -3,152 |
| 202411 | option_value_best_select_learned_exit_5m | 108 | 48.1% | 2.439 | +43,075 | -2,913 |
| 202411 | oracle_best_delta_hard | 108 | 64.8% | 8.229 | +88,408 | -1,290 |
| 202411 | oracle_best_delta_oracle_exit | 108 | 94.4% | 139.355 | +176,063 | -791 |
| 202412 | fixed_delta_0.70_hard | 114 | 72.8% | 4.702 | +56,271 | -1,844 |
| 202412 | fixed_delta_0.70_learned_exit_5m | 114 | 72.8% | 4.689 | +56,067 | -1,844 |
| 202412 | option_value_hold180_select_hard | 114 | 61.4% | 2.943 | +46,110 | -2,321 |
| 202412 | option_value_rule_select_hard | 114 | 63.2% | 3.245 | +50,449 | -2,446 |
| 202412 | option_value_best_select_hard | 114 | 43.9% | 2.103 | +40,351 | -4,455 |
| 202412 | option_value_best_select_learned_exit_5m | 114 | 43.9% | 2.142 | +41,785 | -4,775 |
| 202412 | oracle_best_delta_hard | 114 | 72.8% | 9.408 | +98,878 | -1,005 |
| 202412 | oracle_best_delta_oracle_exit | 114 | 93.0% | 471.996 | +327,038 | -172 |
| 202501 | fixed_delta_0.70_hard | 110 | 79.1% | 8.774 | +80,318 | -1,655 |
| 202501 | fixed_delta_0.70_learned_exit_5m | 110 | 81.8% | 8.654 | +76,778 | -1,655 |
| 202501 | option_value_hold180_select_hard | 110 | 73.6% | 6.397 | +85,351 | -2,264 |
| 202501 | option_value_rule_select_hard | 110 | 73.6% | 6.291 | +84,478 | -2,264 |
| 202501 | option_value_best_select_hard | 110 | 58.2% | 4.039 | +80,722 | -2,264 |
| 202501 | option_value_best_select_learned_exit_5m | 110 | 60.9% | 4.459 | +90,864 | -2,264 |
| 202501 | oracle_best_delta_hard | 110 | 80.0% | 23.193 | +159,874 | -818 |
| 202501 | oracle_best_delta_oracle_exit | 110 | 96.4% | 519.436 | +286,587 | -208 |
| 202502 | fixed_delta_0.70_hard | 102 | 67.6% | 4.808 | +62,514 | -2,077 |
| 202502 | fixed_delta_0.70_learned_exit_5m | 102 | 67.6% | 3.961 | +48,605 | -2,077 |
| 202502 | option_value_hold180_select_hard | 102 | 58.8% | 3.711 | +61,177 | -2,077 |
| 202502 | option_value_rule_select_hard | 102 | 59.8% | 3.844 | +60,146 | -2,077 |
| 202502 | option_value_best_select_hard | 102 | 44.1% | 2.919 | +63,206 | -3,564 |
| 202502 | option_value_best_select_learned_exit_5m | 102 | 46.1% | 2.782 | +58,121 | -3,564 |
| 202502 | oracle_best_delta_hard | 102 | 67.6% | 11.967 | +119,751 | -756 |
| 202502 | oracle_best_delta_oracle_exit | 102 | 94.1% | 547.423 | +323,989 | -190 |
| 202503 | fixed_delta_0.70_hard | 118 | 74.6% | 7.836 | +104,378 | -1,838 |
| 202503 | fixed_delta_0.70_learned_exit_5m | 118 | 75.4% | 6.384 | +81,155 | -1,838 |
| 202503 | option_value_hold180_select_hard | 118 | 65.3% | 5.479 | +104,639 | -2,546 |
| 202503 | option_value_rule_select_hard | 118 | 66.1% | 5.836 | +107,159 | -1,892 |
| 202503 | option_value_best_select_hard | 118 | 56.8% | 4.775 | +111,040 | -4,509 |
| 202503 | option_value_best_select_learned_exit_5m | 118 | 56.8% | 3.886 | +86,149 | -6,091 |
| 202503 | oracle_best_delta_hard | 118 | 74.6% | 15.933 | +158,643 | -1,479 |
| 202503 | oracle_best_delta_oracle_exit | 118 | 99.2% | 3890.021 | +320,377 | -82 |
| 202504 | fixed_delta_0.70_hard | 117 | 73.5% | 5.581 | +127,074 | -4,343 |
| 202504 | fixed_delta_0.70_learned_exit_5m | 117 | 74.4% | 4.056 | +74,997 | -4,343 |
| 202504 | option_value_hold180_select_hard | 117 | 60.7% | 4.051 | +116,707 | -5,119 |
| 202504 | option_value_rule_select_hard | 117 | 61.5% | 4.215 | +120,522 | -4,557 |
| 202504 | option_value_best_select_hard | 117 | 53.8% | 3.638 | +121,898 | -4,343 |
| 202504 | option_value_best_select_learned_exit_5m | 117 | 56.4% | 2.633 | +67,799 | -4,343 |
| 202504 | oracle_best_delta_hard | 117 | 76.1% | 20.498 | +199,924 | -957 |
| 202504 | oracle_best_delta_oracle_exit | 117 | 91.5% | 423.577 | +377,845 | -341 |
| 202505 | fixed_delta_0.70_hard | 119 | 69.7% | 4.118 | +62,197 | -2,609 |
| 202505 | fixed_delta_0.70_learned_exit_5m | 119 | 70.6% | 4.818 | +70,182 | -1,902 |
| 202505 | option_value_hold180_select_hard | 119 | 62.2% | 3.319 | +58,676 | -2,609 |
| 202505 | option_value_rule_select_hard | 119 | 63.0% | 3.382 | +59,391 | -2,609 |
| 202505 | option_value_best_select_hard | 119 | 52.9% | 2.449 | +50,426 | -6,100 |
| 202505 | option_value_best_select_learned_exit_5m | 119 | 53.8% | 3.239 | +74,421 | -5,244 |
| 202505 | oracle_best_delta_hard | 119 | 69.7% | 10.219 | +130,272 | -1,311 |
| 202505 | oracle_best_delta_oracle_exit | 119 | 95.8% | 1084.751 | +268,980 | -109 |
| 202506 | fixed_delta_0.70_hard | 108 | 72.2% | 7.582 | +56,703 | -1,322 |
| 202506 | fixed_delta_0.70_learned_exit_5m | 108 | 73.1% | 8.148 | +58,502 | -1,322 |
| 202506 | option_value_hold180_select_hard | 108 | 62.0% | 4.464 | +61,402 | -2,857 |
| 202506 | option_value_rule_select_hard | 108 | 63.9% | 5.094 | +63,188 | -2,857 |
| 202506 | option_value_best_select_hard | 108 | 47.2% | 2.450 | +46,094 | -5,693 |
| 202506 | option_value_best_select_learned_exit_5m | 108 | 48.1% | 2.786 | +56,022 | -6,045 |
| 202506 | oracle_best_delta_hard | 108 | 72.2% | 15.482 | +106,733 | -630 |
| 202506 | oracle_best_delta_oracle_exit | 108 | 96.3% | 685.439 | +191,593 | -134 |
| 202507 | fixed_delta_0.70_hard | 117 | 73.5% | 4.874 | +46,319 | -1,709 |
| 202507 | fixed_delta_0.70_learned_exit_5m | 117 | 73.5% | 5.116 | +49,222 | -1,709 |
| 202507 | option_value_hold180_select_hard | 117 | 65.0% | 3.896 | +50,028 | -1,534 |
| 202507 | option_value_rule_select_hard | 117 | 65.8% | 3.966 | +50,824 | -1,534 |
| 202507 | option_value_best_select_hard | 117 | 51.3% | 2.123 | +35,041 | -3,249 |
| 202507 | option_value_best_select_learned_exit_5m | 117 | 50.4% | 2.143 | +36,649 | -4,017 |
| 202507 | oracle_best_delta_hard | 117 | 73.5% | 11.333 | +97,394 | -1,144 |
| 202507 | oracle_best_delta_oracle_exit | 117 | 94.9% | 408.413 | +207,820 | -239 |
| 202508 | fixed_delta_0.70_hard | 115 | 69.6% | 3.790 | +30,879 | -3,118 |
| 202508 | fixed_delta_0.70_learned_exit_5m | 115 | 69.6% | 3.877 | +31,845 | -3,118 |
| 202508 | option_value_hold180_select_hard | 115 | 52.2% | 2.252 | +27,577 | -4,468 |
| 202508 | option_value_rule_select_hard | 115 | 53.9% | 2.256 | +26,209 | -4,502 |
| 202508 | option_value_best_select_hard | 115 | 39.1% | 1.491 | +18,459 | -5,674 |
| 202508 | option_value_best_select_learned_exit_5m | 115 | 39.1% | 1.620 | +23,332 | -5,674 |
| 202508 | oracle_best_delta_hard | 115 | 70.4% | 9.518 | +68,657 | -1,294 |
| 202508 | oracle_best_delta_oracle_exit | 115 | 96.5% | 1778.558 | +140,229 | -35 |
| 202509 | fixed_delta_0.70_hard | 113 | 69.0% | 3.536 | +40,353 | -3,227 |
| 202509 | fixed_delta_0.70_learned_exit_5m | 113 | 69.9% | 4.028 | +41,300 | -1,340 |
| 202509 | option_value_hold180_select_hard | 113 | 57.5% | 2.604 | +42,992 | -5,189 |
| 202509 | option_value_rule_select_hard | 113 | 58.4% | 2.703 | +43,902 | -4,123 |
| 202509 | option_value_best_select_hard | 113 | 49.6% | 2.331 | +46,397 | -5,949 |
| 202509 | option_value_best_select_learned_exit_5m | 113 | 49.6% | 2.421 | +47,188 | -5,328 |
| 202509 | oracle_best_delta_hard | 113 | 69.0% | 9.155 | +94,599 | -1,284 |
| 202509 | oracle_best_delta_oracle_exit | 113 | 93.8% | 490.144 | +179,801 | -121 |
| 202510 | fixed_delta_0.70_hard | 126 | 77.0% | 7.295 | +88,317 | -1,692 |
| 202510 | fixed_delta_0.70_learned_exit_5m | 126 | 77.8% | 7.097 | +84,856 | -1,692 |
| 202510 | option_value_hold180_select_hard | 126 | 65.9% | 4.949 | +92,225 | -1,852 |
| 202510 | option_value_rule_select_hard | 126 | 69.8% | 5.899 | +100,218 | -1,852 |
| 202510 | option_value_best_select_hard | 126 | 57.1% | 4.592 | +108,613 | -2,890 |
| 202510 | option_value_best_select_learned_exit_5m | 126 | 57.9% | 4.744 | +114,264 | -2,890 |
| 202510 | oracle_best_delta_hard | 126 | 78.6% | 19.472 | +174,508 | -642 |
| 202510 | oracle_best_delta_oracle_exit | 126 | 93.7% | 503.916 | +346,644 | -162 |
| 202511 | fixed_delta_0.70_hard | 103 | 72.8% | 5.482 | +66,946 | -4,220 |
| 202511 | fixed_delta_0.70_learned_exit_5m | 103 | 75.7% | 7.772 | +77,268 | -2,089 |
| 202511 | option_value_hold180_select_hard | 103 | 62.1% | 4.933 | +83,592 | -4,220 |
| 202511 | option_value_rule_select_hard | 103 | 63.1% | 5.155 | +84,269 | -4,220 |
| 202511 | option_value_best_select_hard | 103 | 55.3% | 4.010 | +88,225 | -4,220 |
| 202511 | option_value_best_select_learned_exit_5m | 103 | 58.3% | 5.071 | +104,982 | -4,158 |
| 202511 | oracle_best_delta_hard | 103 | 73.8% | 20.965 | +149,447 | -970 |
| 202511 | oracle_best_delta_oracle_exit | 103 | 97.1% | 1463.233 | +270,408 | -82 |
| 202512 | fixed_delta_0.70_hard | 116 | 61.2% | 3.245 | +35,749 | -1,506 |
| 202512 | fixed_delta_0.70_learned_exit_5m | 116 | 61.2% | 3.333 | +37,138 | -1,506 |
| 202512 | option_value_hold180_select_hard | 116 | 51.7% | 2.319 | +32,086 | -2,646 |
| 202512 | option_value_rule_select_hard | 116 | 53.4% | 2.408 | +33,041 | -2,531 |
| 202512 | option_value_best_select_hard | 116 | 41.4% | 1.543 | +20,756 | -4,231 |
| 202512 | option_value_best_select_learned_exit_5m | 116 | 41.4% | 1.825 | +31,528 | -4,144 |
| 202512 | oracle_best_delta_hard | 116 | 61.2% | 6.770 | +68,754 | -1,401 |
| 202512 | oracle_best_delta_oracle_exit | 116 | 92.2% | 257.294 | +161,230 | -251 |
| 202601 | fixed_delta_0.70_hard | 101 | 67.3% | 3.186 | +40,481 | -2,913 |
| 202601 | fixed_delta_0.70_learned_exit_5m | 101 | 67.3% | 3.072 | +38,365 | -2,913 |
| 202601 | option_value_hold180_select_hard | 101 | 60.4% | 3.085 | +50,057 | -3,559 |
| 202601 | option_value_rule_select_hard | 101 | 59.4% | 2.937 | +48,215 | -3,559 |
| 202601 | option_value_best_select_hard | 101 | 44.6% | 2.044 | +37,320 | -9,158 |
| 202601 | option_value_best_select_learned_exit_5m | 101 | 44.6% | 2.386 | +49,524 | -9,158 |
| 202601 | oracle_best_delta_hard | 101 | 68.3% | 8.367 | +94,062 | -1,549 |
| 202601 | oracle_best_delta_oracle_exit | 101 | 98.0% | 1706.019 | +230,024 | -111 |
| 202602 | fixed_delta_0.70_hard | 100 | 71.0% | 3.408 | +45,072 | -2,051 |
| 202602 | fixed_delta_0.70_learned_exit_5m | 100 | 71.0% | 3.418 | +45,257 | -2,051 |
| 202602 | option_value_hold180_select_hard | 100 | 65.0% | 3.280 | +56,790 | -3,674 |
| 202602 | option_value_rule_select_hard | 100 | 65.0% | 3.328 | +57,874 | -3,678 |
| 202602 | option_value_best_select_hard | 100 | 54.0% | 2.866 | +60,156 | -5,133 |
| 202602 | option_value_best_select_learned_exit_5m | 100 | 51.0% | 2.348 | +46,134 | -7,802 |
| 202602 | oracle_best_delta_hard | 100 | 71.0% | 9.811 | +108,426 | -1,477 |
| 202602 | oracle_best_delta_oracle_exit | 100 | 92.0% | 213.462 | +182,600 | -218 |
| 202603 | fixed_delta_0.70_hard | 125 | 68.0% | 5.486 | +84,360 | -3,011 |
| 202603 | fixed_delta_0.70_learned_exit_5m | 125 | 68.8% | 5.197 | +73,856 | -3,011 |
| 202603 | option_value_hold180_select_hard | 125 | 56.0% | 3.865 | +85,268 | -4,691 |
| 202603 | option_value_rule_select_hard | 125 | 56.0% | 3.751 | +80,799 | -4,718 |
| 202603 | option_value_best_select_hard | 125 | 42.4% | 2.597 | +70,960 | -6,587 |
| 202603 | option_value_best_select_learned_exit_5m | 125 | 41.6% | 2.166 | +51,498 | -7,487 |
| 202603 | oracle_best_delta_hard | 125 | 68.0% | 13.997 | +160,763 | -1,179 |
| 202603 | oracle_best_delta_oracle_exit | 125 | 95.2% | 589.518 | +373,885 | -225 |
| 202604 | fixed_delta_0.70_hard | 80 | 38.8% | 0.798 | -6,178 | -8,004 |
| 202604 | fixed_delta_0.70_learned_exit_5m | 80 | 40.0% | 0.865 | -3,960 | -6,606 |
| 202604 | option_value_hold180_select_hard | 80 | 37.5% | 0.762 | -7,564 | -8,412 |
| 202604 | option_value_rule_select_hard | 80 | 37.5% | 0.744 | -8,227 | -8,801 |
| 202604 | option_value_best_select_hard | 80 | 30.0% | 0.673 | -12,406 | -12,713 |
| 202604 | option_value_best_select_learned_exit_5m | 80 | 31.2% | 0.738 | -9,613 | -9,613 |
| 202604 | oracle_best_delta_hard | 80 | 40.0% | 2.011 | +22,572 | -3,041 |
| 202604 | oracle_best_delta_oracle_exit | 80 | 81.2% | 58.001 | +83,601 | -335 |
| 202605 | fixed_delta_0.70_hard | 89 | 49.4% | 2.169 | +26,106 | -4,782 |
| 202605 | fixed_delta_0.70_learned_exit_5m | 89 | 50.6% | 1.876 | +19,142 | -4,782 |
| 202605 | option_value_hold180_select_hard | 89 | 46.1% | 1.964 | +24,744 | -5,329 |
| 202605 | option_value_rule_select_hard | 89 | 46.1% | 1.959 | +24,566 | -5,575 |
| 202605 | option_value_best_select_hard | 89 | 39.3% | 1.679 | +22,898 | -8,377 |
| 202605 | option_value_best_select_learned_exit_5m | 89 | 40.4% | 1.507 | +16,870 | -8,377 |
| 202605 | oracle_best_delta_hard | 89 | 50.6% | 4.438 | +64,593 | -4,542 |
| 202605 | oracle_best_delta_oracle_exit | 89 | 85.4% | 113.716 | +157,450 | -283 |
| 202606 | fixed_delta_0.70_hard | 10 | 50.0% | 2.171 | +1,723 | -1,131 |
| 202606 | fixed_delta_0.70_learned_exit_5m | 10 | 50.0% | 2.171 | +1,723 | -1,131 |
| 202606 | option_value_hold180_select_hard | 10 | 40.0% | 1.396 | +882 | -1,250 |
| 202606 | option_value_rule_select_hard | 10 | 40.0% | 1.424 | +927 | -1,250 |
| 202606 | option_value_best_select_hard | 10 | 40.0% | 1.352 | +1,195 | -1,637 |
| 202606 | option_value_best_select_learned_exit_5m | 10 | 40.0% | 1.325 | +1,105 | -1,637 |
| 202606 | oracle_best_delta_hard | 10 | 50.0% | 4.670 | +5,402 | -1,131 |
| 202606 | oracle_best_delta_oracle_exit | 10 | 90.0% | 71.140 | +10,258 | -146 |

## Config

```json
{
  "args": {
    "data": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\training_data\\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet",
    "candidate_labels": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\research_papers\\JEPA\\results\\jepa_full_pipeline_option_policy\\candidate_labels.parquet",
    "output_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\research_papers\\JEPA\\results\\jepa_full_pipeline_option_value_walkforward",
    "train_start_date": "20220801",
    "min_train_months": 12,
    "start_month": "",
    "end_month": "",
    "max_folds": 0,
    "risk_capital": 1000.0,
    "max_hold_minutes": 180,
    "hard_stop_pct": -0.6,
    "min_exit_hold_minutes": 15,
    "exit_margin": -0.3,
    "greeks_cache_size": 60,
    "progress_every": 20,
    "state_chunk_groups": 20,
    "rebuild_state_rows": false,
    "epochs": 8,
    "hidden_dim": 96,
    "market_z_dim": 24,
    "option_z_dim": 12,
    "dynamic_z_dim": 12,
    "dropout": 0.12,
    "lr": 0.0008,
    "weight_decay": 0.0001,
    "dynamic_loss_weight": 0.75,
    "dynamic_target": "future_best",
    "entry_batch_size": 1024,
    "dynamic_batch_size": 8192,
    "predict_batch_size": 4096,
    "max_dynamic_train_rows": 260000,
    "min_val_trades": 12,
    "seed": 7227,
    "device": "cuda",
    "log_every_epochs": 4
  },
  "candidate_rows": 35945,
  "state_rows": 973147,
  "folds": [
    "202308",
    "202309",
    "202310",
    "202311",
    "202312",
    "202401",
    "202402",
    "202403",
    "202404",
    "202405",
    "202406",
    "202407",
    "202408",
    "202409",
    "202410",
    "202411",
    "202412",
    "202501",
    "202502",
    "202503",
    "202504",
    "202505",
    "202506",
    "202507",
    "202508",
    "202509",
    "202510",
    "202511",
    "202512",
    "202601",
    "202602",
    "202603",
    "202604",
    "202605",
    "202606"
  ],
  "market_feature_count": 222,
  "option_feature_count": 31,
  "dynamic_feature_count": 15,
  "policy_metrics": {
    "fixed_delta_0.70_hard": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.7007280291211648,
        "profit_factor": 4.572934601858759,
        "pnl_dollars": 1891655.467609778,
        "max_drawdown": -11064.303057846148,
        "avg_pnl": 491.8500955823656,
        "avg_hold_minutes": 125.30421216848674,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.7057336973478939
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.6989755713159969,
          "profit_factor": 4.62055986375592,
          "pnl_dollars": 463475.9044106934,
          "max_drawdown": -7892.555203009222,
          "avg_pnl": 365.22923909432103,
          "avg_hold_minutes": 124.49960598896769,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.7083180457052798
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.7253218884120172,
          "profit_factor": 4.914478552052783,
          "pnl_dollars": 924431.2752465822,
          "max_drawdown": -5668.925225696294,
          "avg_pnl": 793.5032405550062,
          "avg_hold_minutes": 124.88412017167381,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.7016927038626609
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.6820113314447592,
          "profit_factor": 4.048011715609711,
          "pnl_dollars": 503748.2879525025,
          "max_drawdown": -4968.499041965522,
          "avg_pnl": 356.7622435924239,
          "avg_hold_minutes": 126.37393767705383,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.7067451841359773
        }
      }
    },
    "fixed_delta_0.70_learned_exit_5m": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.7090483619344774,
        "profit_factor": 4.444481589296,
        "pnl_dollars": 1755495.467609778,
        "max_drawdown": -11374.407975459239,
        "avg_pnl": 456.44707946172076,
        "avg_hold_minutes": 117.64690587623505,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.7057336973478939
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.7021276595744681,
          "profit_factor": 4.494223682997128,
          "pnl_dollars": 441406.4044106934,
          "max_drawdown": -7892.555203009222,
          "avg_pnl": 347.8379861392383,
          "avg_hold_minutes": 120.33490937746257,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.7083180457052798
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.7459227467811159,
          "profit_factor": 4.714163053765356,
          "pnl_dollars": 814633.7752465822,
          "max_drawdown": -5668.925225696294,
          "avg_pnl": 699.2564594391264,
          "avg_hold_minutes": 108.54506437768241,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.7016927038626609
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.6848441926345609,
          "profit_factor": 4.0454932690857115,
          "pnl_dollars": 499455.2879525025,
          "max_drawdown": -4968.499041965522,
          "avg_pnl": 353.72187532046917,
          "avg_hold_minutes": 122.74079320113314,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.7067451841359773
        }
      }
    },
    "option_value_hold180_select_hard": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.5998439937597504,
        "profit_factor": 3.4560165440020043,
        "pnl_dollars": 1929068.7185350782,
        "max_drawdown": -12998.848132152809,
        "avg_pnl": 501.5779299363178,
        "avg_hold_minutes": 116.85647425897037,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.5734380135205408
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.582348305752561,
          "profit_factor": 3.170699349728609,
          "pnl_dollars": 501771.4217049593,
          "max_drawdown": -8376.68826858775,
          "avg_pnl": 395.40695169815547,
          "avg_hold_minutes": 114.30260047281324,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.5561512214342
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.6420600858369099,
          "profit_factor": 3.949290516573601,
          "pnl_dollars": 846803.6322004187,
          "max_drawdown": -6243.721350676031,
          "avg_pnl": 726.8700705582994,
          "avg_hold_minutes": 119.09871244635193,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.6126924463519313
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.5807365439093485,
          "profit_factor": 3.1727628872571576,
          "pnl_dollars": 580493.6646297004,
          "max_drawdown": -5825.786787477089,
          "avg_pnl": 411.1144933638105,
          "avg_hold_minutes": 117.30169971671388,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.5565864022662889
        }
      }
    },
    "option_value_rule_select_hard": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.6123244929797191,
        "profit_factor": 3.562563366299591,
        "pnl_dollars": 1943340.9063307275,
        "max_drawdown": -13907.521407101303,
        "avg_pnl": 505.2888471998771,
        "avg_hold_minutes": 117.7145085803432,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.588008710348414
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.5965327029156816,
          "profit_factor": 3.2541700546635886,
          "pnl_dollars": 498375.26980242424,
          "max_drawdown": -9011.710932980583,
          "avg_pnl": 392.7307090641641,
          "avg_hold_minutes": 115.44523246650907,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.5717430260047281
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.655793991416309,
          "profit_factor": 4.122711040602566,
          "pnl_dollars": 874380.1885999638,
          "max_drawdown": -6243.721350676031,
          "avg_pnl": 750.5409344205698,
          "avg_hold_minutes": 119.45493562231759,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.6224677253218884
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.5906515580736544,
          "profit_factor": 3.217923794929121,
          "pnl_dollars": 570585.4479283397,
          "max_drawdown": -5794.843175795628,
          "avg_pnl": 404.0973427254531,
          "avg_hold_minutes": 118.31798866855524,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.5741959631728045
        }
      }
    },
    "option_value_best_select_hard": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.4750390015600624,
        "profit_factor": 2.483421256749396,
        "pnl_dollars": 1751373.8079750678,
        "max_drawdown": -20782.87901171134,
        "avg_pnl": 455.3754050897212,
        "avg_hold_minutes": 105.28471138845553,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.41813169526781074
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.4373522458628842,
          "profit_factor": 2.0792175300841937,
          "pnl_dollars": 418879.1663046287,
          "max_drawdown": -14164.217310841894,
          "avg_pnl": 330.08602545676024,
          "avg_hold_minutes": 99.17257683215131,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.3665964539007093
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.5682403433476395,
          "profit_factor": 3.300106129429611,
          "pnl_dollars": 825400.1872028706,
          "max_drawdown": -5949.083374711452,
          "avg_pnl": 708.4980147664126,
          "avg_hold_minutes": 114.44206008583691,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.548474077253219
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.43201133144475923,
          "profit_factor": 2.169373982582905,
          "pnl_dollars": 507094.4544675685,
          "max_drawdown": -9253.376738486113,
          "avg_pnl": 359.13204990621,
          "avg_hold_minutes": 103.22237960339943,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.3569060198300284
        }
      }
    },
    "option_value_best_select_learned_exit_5m": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.48023920956838273,
        "profit_factor": 2.4638616243489326,
        "pnl_dollars": 1706676.807975068,
        "max_drawdown": -17989.37901171134,
        "avg_pnl": 443.7537202223266,
        "avg_hold_minutes": 100.15080603224129,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.41813169526781074
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.43577620173364856,
          "profit_factor": 2.0258427837194106,
          "pnl_dollars": 399102.1663046287,
          "max_drawdown": -14511.367532809207,
          "avg_pnl": 314.5013130848138,
          "avg_hold_minutes": 98.096926713948,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.3665964539007093
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.5888412017167381,
          "profit_factor": 3.3155517691493044,
          "pnl_dollars": 791157.6872028706,
          "max_drawdown": -5734.641311825952,
          "avg_pnl": 679.1053109037516,
          "avg_hold_minutes": 100.3862660944206,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.548474077253219
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.43059490084985835,
          "profit_factor": 2.186746318742251,
          "pnl_dollars": 516416.95446756855,
          "max_drawdown": -9253.376738486113,
          "avg_pnl": 365.7343870166916,
          "avg_hold_minutes": 101.80240793201133,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.3569060198300284
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.7054082163286531,
        "profit_factor": 11.120046504759102,
        "pnl_dollars": 3893655.8155947844,
        "max_drawdown": -7506.662585620768,
        "avg_pnl": 1012.3910076949518,
        "avg_hold_minutes": 114.48647945917837,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.5262211648465939
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.7037037037037037,
          "profit_factor": 10.155880032080715,
          "pnl_dollars": 1122393.7688288782,
          "max_drawdown": -5502.185210110154,
          "avg_pnl": 884.4710550266967,
          "avg_hold_minutes": 114.6729708431836,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.5223026004728133
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.7321888412017168,
          "profit_factor": 15.442599798255888,
          "pnl_dollars": 1507035.3265080433,
          "max_drawdown": -1861.9406562426593,
          "avg_pnl": 1293.5925549425265,
          "avg_hold_minutes": 112.20171673819742,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.5406811158798284
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.6848441926345609,
          "profit_factor": 9.010912058318478,
          "pnl_dollars": 1264226.720257863,
          "max_drawdown": -3447.943480726797,
          "avg_pnl": 895.3447027321976,
          "avg_hold_minutes": 116.20396600566572,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.5178123937677054
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 3846,
        "win_rate": 0.9412376495059802,
        "profit_factor": 437.53299184587735,
        "pnl_dollars": 8817798.433857948,
        "max_drawdown": -790.7288921130821,
        "avg_pnl": 2292.7193015751295,
        "avg_hold_minutes": 85.45891835673427,
        "long_rate": 0.5358814352574103,
        "avg_delta_abs": 0.39497160686427457
      },
      "per_ticker": {
        "QQQ": {
          "trades": 1269,
          "win_rate": 0.950354609929078,
          "profit_factor": 472.51639064111475,
          "pnl_dollars": 2659314.2196473,
          "max_drawdown": -409.52268744656976,
          "avg_pnl": 2095.598281833964,
          "avg_hold_minutes": 83.2033096926714,
          "long_rate": 0.5263987391646966,
          "avg_delta_abs": 0.36210937746256894
        },
        "SPX": {
          "trades": 1165,
          "win_rate": 0.9467811158798283,
          "profit_factor": 555.4388809588875,
          "pnl_dollars": 3246950.511503566,
          "max_drawdown": -790.7288921130821,
          "avg_pnl": 2787.081984123233,
          "avg_hold_minutes": 90.36909871244636,
          "long_rate": 0.5381974248927038,
          "avg_delta_abs": 0.46962248927038625
        },
        "SPY": {
          "trades": 1412,
          "win_rate": 0.9284702549575071,
          "profit_factor": 335.527769904704,
          "pnl_dollars": 2911533.702707081,
          "max_drawdown": -295.2827276333119,
          "avg_pnl": 2061.9927072996325,
          "avg_hold_minutes": 83.43484419263456,
          "long_rate": 0.5424929178470255,
          "avg_delta_abs": 0.36291345609065156
        }
      }
    }
  }
}
```
