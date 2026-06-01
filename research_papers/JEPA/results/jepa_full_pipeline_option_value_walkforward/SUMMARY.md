# OptionValueJEPA Walk-Forward Since 2022

Candidate labels: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\results\jepa_full_pipeline_option_policy\candidate_labels.parquet`
Train start: `20220801`
Min train months: `12`
Epochs per fold: `8`
Exit margin: `-0.3`

## Overall Walk-Forward Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 2100 | 74.3% | 5.761 | +1,171,610 | -5,546 | +558 | 169.3 | 0.703 |
| fixed_delta_0.70_learned_exit_5m | 2100 | 75.1% | 5.398 | +1,055,623 | -5,546 | +503 | 155.8 | 0.703 |
| option_value_hold180_select_hard | 2100 | 65.8% | 4.414 | +1,199,159 | -5,546 | +571 | 159.3 | 0.572 |
| option_value_rule_select_hard | 2100 | 66.0% | 4.415 | +1,187,154 | -5,546 | +565 | 159.8 | 0.578 |
| option_value_best_select_hard | 2100 | 51.8% | 2.937 | +1,106,884 | -8,180 | +527 | 143.3 | 0.399 |
| option_value_best_select_learned_exit_5m | 2100 | 52.9% | 2.829 | +1,028,827 | -8,769 | +490 | 133.2 | 0.399 |
| oracle_best_delta_hard | 2100 | 74.5% | 13.993 | +2,084,499 | -2,093 | +993 | 155.1 | 0.531 |
| oracle_best_delta_oracle_exit | 2100 | 95.9% | 643.432 | +4,256,509 | -342 | +2,027 | 114.6 | 0.387 |

## Fold Metrics

| Month | Policy | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202308 | fixed_delta_0.70_hard | 68 | 70.6% | 5.528 | +25,639 | -1,595 |
| 202308 | fixed_delta_0.70_learned_exit_5m | 68 | 73.5% | 6.375 | +28,222 | -1,595 |
| 202308 | option_value_hold180_select_hard | 68 | 66.2% | 3.536 | +23,263 | -1,974 |
| 202308 | option_value_rule_select_hard | 68 | 66.2% | 3.831 | +24,664 | -1,724 |
| 202308 | option_value_best_select_hard | 68 | 50.0% | 2.026 | +18,037 | -2,941 |
| 202308 | option_value_best_select_learned_exit_5m | 68 | 50.0% | 2.060 | +18,642 | -2,941 |
| 202308 | oracle_best_delta_hard | 68 | 70.6% | 11.697 | +49,152 | -1,034 |
| 202308 | oracle_best_delta_oracle_exit | 68 | 98.5% | 11085.873 | +101,623 | -9 |
| 202309 | fixed_delta_0.70_hard | 60 | 65.0% | 3.077 | +17,630 | -1,231 |
| 202309 | fixed_delta_0.70_learned_exit_5m | 60 | 65.0% | 2.835 | +15,574 | -1,231 |
| 202309 | option_value_hold180_select_hard | 60 | 53.3% | 2.688 | +19,373 | -2,134 |
| 202309 | option_value_rule_select_hard | 60 | 58.3% | 2.985 | +19,747 | -1,217 |
| 202309 | option_value_best_select_hard | 60 | 40.0% | 1.637 | +12,646 | -3,951 |
| 202309 | option_value_best_select_learned_exit_5m | 60 | 40.0% | 1.489 | +9,713 | -3,951 |
| 202309 | oracle_best_delta_hard | 60 | 65.0% | 6.722 | +36,610 | -1,207 |
| 202309 | oracle_best_delta_oracle_exit | 60 | 88.3% | 101.022 | +76,210 | -216 |
| 202310 | fixed_delta_0.70_hard | 66 | 66.7% | 4.174 | +40,067 | -5,122 |
| 202310 | fixed_delta_0.70_learned_exit_5m | 66 | 66.7% | 3.907 | +36,698 | -5,122 |
| 202310 | option_value_hold180_select_hard | 66 | 63.6% | 4.134 | +45,199 | -5,122 |
| 202310 | option_value_rule_select_hard | 66 | 63.6% | 3.881 | +43,404 | -5,122 |
| 202310 | option_value_best_select_hard | 66 | 51.5% | 3.352 | +50,000 | -6,267 |
| 202310 | option_value_best_select_learned_exit_5m | 66 | 54.5% | 3.443 | +49,844 | -6,267 |
| 202310 | oracle_best_delta_hard | 66 | 66.7% | 10.369 | +76,602 | -1,979 |
| 202310 | oracle_best_delta_oracle_exit | 66 | 90.9% | 890.445 | +177,524 | -134 |
| 202311 | fixed_delta_0.70_hard | 63 | 74.6% | 5.868 | +25,741 | -851 |
| 202311 | fixed_delta_0.70_learned_exit_5m | 63 | 74.6% | 5.718 | +24,947 | -851 |
| 202311 | option_value_hold180_select_hard | 63 | 65.1% | 4.637 | +26,184 | -1,223 |
| 202311 | option_value_rule_select_hard | 63 | 65.1% | 4.415 | +24,286 | -1,223 |
| 202311 | option_value_best_select_hard | 63 | 55.6% | 2.727 | +25,299 | -2,293 |
| 202311 | option_value_best_select_learned_exit_5m | 63 | 57.1% | 2.644 | +22,769 | -1,895 |
| 202311 | oracle_best_delta_hard | 63 | 74.6% | 10.519 | +47,433 | -851 |
| 202311 | oracle_best_delta_oracle_exit | 63 | 95.2% | 385.207 | +115,398 | -123 |
| 202312 | fixed_delta_0.70_hard | 59 | 83.1% | 8.141 | +25,379 | -1,002 |
| 202312 | fixed_delta_0.70_learned_exit_5m | 59 | 83.1% | 8.666 | +27,246 | -1,002 |
| 202312 | option_value_hold180_select_hard | 59 | 71.2% | 3.747 | +20,206 | -1,162 |
| 202312 | option_value_rule_select_hard | 59 | 72.9% | 4.240 | +21,601 | -1,080 |
| 202312 | option_value_best_select_hard | 59 | 50.8% | 2.010 | +13,995 | -3,604 |
| 202312 | option_value_best_select_learned_exit_5m | 59 | 50.8% | 2.428 | +19,786 | -3,604 |
| 202312 | oracle_best_delta_hard | 59 | 83.1% | 19.268 | +49,736 | -629 |
| 202312 | oracle_best_delta_oracle_exit | 59 | 100.0% | nan | +83,091 | +0 |
| 202401 | fixed_delta_0.70_hard | 63 | 84.1% | 13.838 | +45,294 | -824 |
| 202401 | fixed_delta_0.70_learned_exit_5m | 63 | 84.1% | 13.312 | +43,345 | -824 |
| 202401 | option_value_hold180_select_hard | 63 | 79.4% | 14.842 | +55,947 | -824 |
| 202401 | option_value_rule_select_hard | 63 | 81.0% | 14.835 | +58,929 | -824 |
| 202401 | option_value_best_select_hard | 63 | 66.7% | 7.575 | +62,891 | -1,445 |
| 202401 | option_value_best_select_learned_exit_5m | 63 | 66.7% | 7.554 | +58,977 | -1,445 |
| 202401 | oracle_best_delta_hard | 63 | 84.1% | 30.375 | +90,726 | -629 |
| 202401 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +153,426 | +0 |
| 202402 | fixed_delta_0.70_hard | 60 | 81.7% | 10.974 | +37,684 | -863 |
| 202402 | fixed_delta_0.70_learned_exit_5m | 60 | 83.3% | 11.040 | +37,881 | -863 |
| 202402 | option_value_hold180_select_hard | 60 | 78.3% | 8.040 | +41,059 | -1,368 |
| 202402 | option_value_rule_select_hard | 60 | 78.3% | 7.560 | +39,957 | -1,368 |
| 202402 | option_value_best_select_hard | 60 | 60.0% | 4.338 | +38,546 | -2,310 |
| 202402 | option_value_best_select_learned_exit_5m | 60 | 61.7% | 4.338 | +38,532 | -2,310 |
| 202402 | oracle_best_delta_hard | 60 | 81.7% | 22.205 | +72,395 | -863 |
| 202402 | oracle_best_delta_oracle_exit | 60 | 96.7% | 409.816 | +116,332 | -144 |
| 202403 | fixed_delta_0.70_hard | 60 | 81.7% | 5.501 | +19,681 | -1,631 |
| 202403 | fixed_delta_0.70_learned_exit_5m | 60 | 81.7% | 6.381 | +23,527 | -1,631 |
| 202403 | option_value_hold180_select_hard | 60 | 76.7% | 5.122 | +21,616 | -1,722 |
| 202403 | option_value_rule_select_hard | 60 | 71.7% | 4.464 | +19,956 | -1,722 |
| 202403 | option_value_best_select_hard | 60 | 48.3% | 2.014 | +14,068 | -2,565 |
| 202403 | option_value_best_select_learned_exit_5m | 60 | 48.3% | 2.167 | +16,182 | -2,565 |
| 202403 | oracle_best_delta_hard | 60 | 81.7% | 12.503 | +38,518 | -993 |
| 202403 | oracle_best_delta_oracle_exit | 60 | 93.3% | 386.165 | +92,858 | -110 |
| 202404 | fixed_delta_0.70_hard | 65 | 72.3% | 6.892 | +43,237 | -2,086 |
| 202404 | fixed_delta_0.70_learned_exit_5m | 65 | 73.8% | 7.381 | +35,696 | -2,086 |
| 202404 | option_value_hold180_select_hard | 65 | 60.0% | 4.955 | +43,644 | -2,454 |
| 202404 | option_value_rule_select_hard | 65 | 56.9% | 4.794 | +42,409 | -2,633 |
| 202404 | option_value_best_select_hard | 65 | 43.1% | 2.640 | +33,169 | -4,821 |
| 202404 | option_value_best_select_learned_exit_5m | 65 | 44.6% | 3.030 | +37,512 | -4,821 |
| 202404 | oracle_best_delta_hard | 65 | 72.3% | 15.123 | +68,389 | -1,136 |
| 202404 | oracle_best_delta_oracle_exit | 65 | 96.9% | 1186.668 | +234,674 | -116 |
| 202405 | fixed_delta_0.70_hard | 66 | 69.7% | 6.275 | +28,378 | -1,483 |
| 202405 | fixed_delta_0.70_learned_exit_5m | 66 | 71.2% | 5.483 | +23,802 | -1,273 |
| 202405 | option_value_hold180_select_hard | 66 | 60.6% | 4.103 | +27,793 | -2,007 |
| 202405 | option_value_rule_select_hard | 66 | 60.6% | 4.048 | +27,382 | -2,007 |
| 202405 | option_value_best_select_hard | 66 | 51.5% | 2.145 | +19,379 | -3,162 |
| 202405 | option_value_best_select_learned_exit_5m | 66 | 53.0% | 1.853 | +14,374 | -3,162 |
| 202405 | oracle_best_delta_hard | 66 | 69.7% | 9.505 | +41,173 | -1,093 |
| 202405 | oracle_best_delta_oracle_exit | 66 | 92.4% | 401.349 | +98,201 | -179 |
| 202406 | fixed_delta_0.70_hard | 57 | 78.9% | 6.928 | +27,668 | -875 |
| 202406 | fixed_delta_0.70_learned_exit_5m | 57 | 78.9% | 7.142 | +28,669 | -875 |
| 202406 | option_value_hold180_select_hard | 57 | 70.2% | 6.872 | +38,135 | -1,819 |
| 202406 | option_value_rule_select_hard | 57 | 71.9% | 7.142 | +38,796 | -1,819 |
| 202406 | option_value_best_select_hard | 57 | 56.1% | 3.617 | +30,896 | -2,587 |
| 202406 | option_value_best_select_learned_exit_5m | 57 | 59.6% | 3.802 | +32,463 | -2,587 |
| 202406 | oracle_best_delta_hard | 57 | 78.9% | 16.234 | +56,199 | -744 |
| 202406 | oracle_best_delta_oracle_exit | 57 | 100.0% | nan | +183,763 | +0 |
| 202407 | fixed_delta_0.70_hard | 66 | 77.3% | 3.565 | +23,801 | -4,455 |
| 202407 | fixed_delta_0.70_learned_exit_5m | 66 | 77.3% | 3.521 | +23,388 | -4,455 |
| 202407 | option_value_hold180_select_hard | 66 | 65.2% | 3.090 | +26,045 | -4,455 |
| 202407 | option_value_rule_select_hard | 66 | 65.2% | 3.036 | +25,391 | -4,653 |
| 202407 | option_value_best_select_hard | 66 | 45.5% | 1.976 | +21,285 | -4,895 |
| 202407 | option_value_best_select_learned_exit_5m | 66 | 42.4% | 1.773 | +17,521 | -4,895 |
| 202407 | oracle_best_delta_hard | 66 | 77.3% | 11.805 | +60,756 | -969 |
| 202407 | oracle_best_delta_oracle_exit | 66 | 95.5% | 315.692 | +115,699 | -156 |
| 202408 | fixed_delta_0.70_hard | 66 | 74.2% | 5.486 | +36,091 | -3,233 |
| 202408 | fixed_delta_0.70_learned_exit_5m | 66 | 74.2% | 4.125 | +25,136 | -3,233 |
| 202408 | option_value_hold180_select_hard | 66 | 60.6% | 2.763 | +26,166 | -4,561 |
| 202408 | option_value_rule_select_hard | 66 | 57.6% | 2.450 | +23,373 | -5,410 |
| 202408 | option_value_best_select_hard | 66 | 48.5% | 2.327 | +28,501 | -3,463 |
| 202408 | option_value_best_select_learned_exit_5m | 66 | 48.5% | 1.831 | +17,849 | -3,368 |
| 202408 | oracle_best_delta_hard | 66 | 74.2% | 12.736 | +55,881 | -900 |
| 202408 | oracle_best_delta_oracle_exit | 66 | 92.4% | 342.088 | +118,528 | -138 |
| 202409 | fixed_delta_0.70_hard | 60 | 83.3% | 22.453 | +43,979 | -685 |
| 202409 | fixed_delta_0.70_learned_exit_5m | 60 | 83.3% | 20.590 | +40,158 | -685 |
| 202409 | option_value_hold180_select_hard | 60 | 73.3% | 8.911 | +44,183 | -739 |
| 202409 | option_value_rule_select_hard | 60 | 68.3% | 6.680 | +39,244 | -1,195 |
| 202409 | option_value_best_select_hard | 60 | 50.0% | 3.042 | +33,569 | -4,549 |
| 202409 | option_value_best_select_learned_exit_5m | 60 | 51.7% | 2.960 | +31,448 | -4,549 |
| 202409 | oracle_best_delta_hard | 60 | 83.3% | 39.038 | +71,261 | -584 |
| 202409 | oracle_best_delta_oracle_exit | 60 | 98.3% | 20599.806 | +141,809 | -7 |
| 202410 | fixed_delta_0.70_hard | 69 | 81.2% | 14.039 | +39,042 | -925 |
| 202410 | fixed_delta_0.70_learned_exit_5m | 69 | 81.2% | 13.581 | +37,669 | -925 |
| 202410 | option_value_hold180_select_hard | 69 | 71.0% | 5.098 | +36,770 | -2,121 |
| 202410 | option_value_rule_select_hard | 69 | 69.6% | 5.457 | +36,528 | -2,055 |
| 202410 | option_value_best_select_hard | 69 | 55.1% | 3.517 | +33,909 | -3,996 |
| 202410 | option_value_best_select_learned_exit_5m | 69 | 55.1% | 3.756 | +37,129 | -3,996 |
| 202410 | oracle_best_delta_hard | 69 | 81.2% | 29.954 | +62,684 | -452 |
| 202410 | oracle_best_delta_oracle_exit | 69 | 97.1% | 2965.577 | +115,797 | -24 |
| 202411 | fixed_delta_0.70_hard | 60 | 68.3% | 4.547 | +25,702 | -2,092 |
| 202411 | fixed_delta_0.70_learned_exit_5m | 60 | 71.7% | 5.651 | +33,183 | -2,092 |
| 202411 | option_value_hold180_select_hard | 60 | 63.3% | 4.341 | +27,037 | -1,317 |
| 202411 | option_value_rule_select_hard | 60 | 61.7% | 4.168 | +26,451 | -1,317 |
| 202411 | option_value_best_select_hard | 60 | 60.0% | 4.089 | +39,059 | -1,873 |
| 202411 | option_value_best_select_learned_exit_5m | 60 | 65.0% | 5.022 | +46,177 | -1,736 |
| 202411 | oracle_best_delta_hard | 60 | 70.0% | 14.827 | +75,311 | -1,206 |
| 202411 | oracle_best_delta_oracle_exit | 60 | 98.3% | 580.346 | +108,296 | -187 |
| 202412 | fixed_delta_0.70_hard | 62 | 82.3% | 6.313 | +27,375 | -996 |
| 202412 | fixed_delta_0.70_learned_exit_5m | 62 | 83.9% | 6.325 | +27,382 | -1,007 |
| 202412 | option_value_hold180_select_hard | 62 | 72.6% | 4.640 | +27,776 | -1,277 |
| 202412 | option_value_rule_select_hard | 62 | 72.6% | 4.628 | +27,685 | -1,277 |
| 202412 | option_value_best_select_hard | 62 | 54.8% | 2.514 | +20,708 | -1,865 |
| 202412 | option_value_best_select_learned_exit_5m | 62 | 58.1% | 2.335 | +17,858 | -1,865 |
| 202412 | oracle_best_delta_hard | 62 | 82.3% | 13.871 | +54,657 | -889 |
| 202412 | oracle_best_delta_oracle_exit | 62 | 98.4% | 1660.548 | +91,034 | -55 |
| 202501 | fixed_delta_0.70_hard | 60 | 75.0% | 8.019 | +47,721 | -1,655 |
| 202501 | fixed_delta_0.70_learned_exit_5m | 60 | 76.7% | 7.461 | +42,005 | -1,655 |
| 202501 | option_value_hold180_select_hard | 60 | 68.3% | 5.988 | +47,943 | -1,712 |
| 202501 | option_value_rule_select_hard | 60 | 70.0% | 6.301 | +47,423 | -1,655 |
| 202501 | option_value_best_select_hard | 60 | 56.7% | 3.885 | +50,147 | -4,903 |
| 202501 | option_value_best_select_learned_exit_5m | 60 | 58.3% | 3.708 | +45,076 | -4,351 |
| 202501 | oracle_best_delta_hard | 60 | 76.7% | 23.465 | +88,626 | -580 |
| 202501 | oracle_best_delta_oracle_exit | 60 | 96.7% | 382.901 | +152,963 | -208 |
| 202502 | fixed_delta_0.70_hard | 57 | 80.7% | 6.955 | +35,658 | -2,216 |
| 202502 | fixed_delta_0.70_learned_exit_5m | 57 | 80.7% | 6.547 | +33,217 | -2,216 |
| 202502 | option_value_hold180_select_hard | 57 | 66.7% | 4.642 | +36,597 | -3,398 |
| 202502 | option_value_rule_select_hard | 57 | 64.9% | 4.332 | +35,464 | -3,398 |
| 202502 | option_value_best_select_hard | 57 | 52.6% | 2.955 | +32,679 | -4,197 |
| 202502 | option_value_best_select_learned_exit_5m | 57 | 54.4% | 3.167 | +36,118 | -4,197 |
| 202502 | oracle_best_delta_hard | 57 | 80.7% | 17.040 | +57,820 | -600 |
| 202502 | oracle_best_delta_oracle_exit | 57 | 96.5% | 1151.387 | +151,151 | -74 |
| 202503 | fixed_delta_0.70_hard | 63 | 87.3% | 12.883 | +78,898 | -3,148 |
| 202503 | fixed_delta_0.70_learned_exit_5m | 63 | 87.3% | 9.639 | +57,358 | -3,148 |
| 202503 | option_value_hold180_select_hard | 63 | 81.0% | 11.471 | +85,036 | -3,148 |
| 202503 | option_value_rule_select_hard | 63 | 81.0% | 11.596 | +86,048 | -3,148 |
| 202503 | option_value_best_select_hard | 63 | 65.1% | 6.776 | +81,253 | -3,720 |
| 202503 | option_value_best_select_learned_exit_5m | 63 | 65.1% | 5.145 | +58,311 | -3,720 |
| 202503 | oracle_best_delta_hard | 63 | 87.3% | 37.693 | +114,485 | -472 |
| 202503 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +180,300 | +0 |
| 202504 | fixed_delta_0.70_hard | 60 | 81.7% | 6.746 | +92,791 | -5,032 |
| 202504 | fixed_delta_0.70_learned_exit_5m | 60 | 81.7% | 4.202 | +51,706 | -5,032 |
| 202504 | option_value_hold180_select_hard | 60 | 71.7% | 5.897 | +97,889 | -5,032 |
| 202504 | option_value_rule_select_hard | 60 | 71.7% | 5.820 | +97,445 | -5,032 |
| 202504 | option_value_best_select_hard | 60 | 56.7% | 5.338 | +95,685 | -3,892 |
| 202504 | option_value_best_select_learned_exit_5m | 60 | 56.7% | 3.895 | +63,858 | -3,892 |
| 202504 | oracle_best_delta_hard | 60 | 85.0% | 37.361 | +137,443 | -570 |
| 202504 | oracle_best_delta_oracle_exit | 60 | 93.3% | 588.020 | +249,111 | -168 |
| 202505 | fixed_delta_0.70_hard | 63 | 74.6% | 7.812 | +35,841 | -1,725 |
| 202505 | fixed_delta_0.70_learned_exit_5m | 63 | 77.8% | 8.750 | +38,916 | -1,725 |
| 202505 | option_value_hold180_select_hard | 63 | 63.5% | 4.776 | +32,753 | -1,725 |
| 202505 | option_value_rule_select_hard | 63 | 68.3% | 5.234 | +32,601 | -1,725 |
| 202505 | option_value_best_select_hard | 63 | 47.6% | 3.530 | +36,357 | -2,660 |
| 202505 | option_value_best_select_learned_exit_5m | 63 | 50.8% | 3.993 | +43,031 | -2,646 |
| 202505 | oracle_best_delta_hard | 63 | 74.6% | 22.747 | +71,426 | -645 |
| 202505 | oracle_best_delta_oracle_exit | 63 | 98.4% | 2535.697 | +149,233 | -59 |
| 202506 | fixed_delta_0.70_hard | 60 | 73.3% | 7.107 | +33,027 | -1,753 |
| 202506 | fixed_delta_0.70_learned_exit_5m | 60 | 75.0% | 7.578 | +32,743 | -1,322 |
| 202506 | option_value_hold180_select_hard | 60 | 66.7% | 4.967 | +36,107 | -1,924 |
| 202506 | option_value_rule_select_hard | 60 | 65.0% | 4.764 | +35,039 | -1,924 |
| 202506 | option_value_best_select_hard | 60 | 48.3% | 3.123 | +31,410 | -1,753 |
| 202506 | option_value_best_select_learned_exit_5m | 60 | 51.7% | 3.285 | +32,399 | -1,672 |
| 202506 | oracle_best_delta_hard | 60 | 73.3% | 13.814 | +53,346 | -958 |
| 202506 | oracle_best_delta_oracle_exit | 60 | 95.0% | 1927.640 | +98,648 | -24 |
| 202507 | fixed_delta_0.70_hard | 66 | 78.8% | 7.445 | +28,097 | -1,418 |
| 202507 | fixed_delta_0.70_learned_exit_5m | 66 | 78.8% | 6.777 | +25,186 | -1,418 |
| 202507 | option_value_hold180_select_hard | 66 | 74.2% | 5.155 | +26,223 | -834 |
| 202507 | option_value_rule_select_hard | 66 | 72.7% | 5.116 | +25,732 | -834 |
| 202507 | option_value_best_select_hard | 66 | 56.1% | 2.274 | +17,972 | -2,228 |
| 202507 | option_value_best_select_learned_exit_5m | 66 | 57.6% | 2.475 | +19,928 | -2,228 |
| 202507 | oracle_best_delta_hard | 66 | 78.8% | 12.612 | +38,440 | -566 |
| 202507 | oracle_best_delta_oracle_exit | 66 | 98.5% | 707.565 | +83,050 | -118 |
| 202508 | fixed_delta_0.70_hard | 63 | 68.3% | 4.155 | +19,624 | -950 |
| 202508 | fixed_delta_0.70_learned_exit_5m | 63 | 69.8% | 4.913 | +22,769 | -950 |
| 202508 | option_value_hold180_select_hard | 63 | 55.6% | 2.279 | +13,530 | -2,000 |
| 202508 | option_value_rule_select_hard | 63 | 58.7% | 2.907 | +16,159 | -950 |
| 202508 | option_value_best_select_hard | 63 | 49.2% | 1.566 | +9,282 | -3,860 |
| 202508 | option_value_best_select_learned_exit_5m | 63 | 50.8% | 1.793 | +12,679 | -3,530 |
| 202508 | oracle_best_delta_hard | 63 | 68.3% | 5.994 | +27,185 | -640 |
| 202508 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +60,602 | +0 |
| 202509 | fixed_delta_0.70_hard | 62 | 77.4% | 13.267 | +36,057 | -781 |
| 202509 | fixed_delta_0.70_learned_exit_5m | 62 | 77.4% | 13.369 | +36,354 | -781 |
| 202509 | option_value_hold180_select_hard | 62 | 74.2% | 10.661 | +41,744 | -1,187 |
| 202509 | option_value_rule_select_hard | 62 | 74.2% | 10.224 | +40,374 | -1,187 |
| 202509 | option_value_best_select_hard | 62 | 61.3% | 4.199 | +35,929 | -3,244 |
| 202509 | option_value_best_select_learned_exit_5m | 62 | 61.3% | 4.708 | +41,650 | -3,244 |
| 202509 | oracle_best_delta_hard | 62 | 77.4% | 20.799 | +56,066 | -717 |
| 202509 | oracle_best_delta_oracle_exit | 62 | 96.8% | 559.154 | +104,486 | -99 |
| 202510 | fixed_delta_0.70_hard | 67 | 89.6% | 29.078 | +63,291 | -1,667 |
| 202510 | fixed_delta_0.70_learned_exit_5m | 67 | 89.6% | 26.890 | +58,358 | -1,667 |
| 202510 | option_value_hold180_select_hard | 67 | 80.6% | 16.210 | +68,347 | -1,667 |
| 202510 | option_value_rule_select_hard | 67 | 82.1% | 18.603 | +67,723 | -1,667 |
| 202510 | option_value_best_select_hard | 67 | 76.1% | 11.868 | +76,561 | -1,667 |
| 202510 | option_value_best_select_learned_exit_5m | 67 | 76.1% | 12.013 | +77,588 | -1,667 |
| 202510 | oracle_best_delta_hard | 67 | 89.6% | 122.060 | +117,825 | -386 |
| 202510 | oracle_best_delta_oracle_exit | 67 | 97.0% | 1349.134 | +197,040 | -78 |
| 202511 | fixed_delta_0.70_hard | 57 | 78.9% | 11.588 | +53,797 | -2,235 |
| 202511 | fixed_delta_0.70_learned_exit_5m | 57 | 78.9% | 9.382 | +42,589 | -2,235 |
| 202511 | option_value_hold180_select_hard | 57 | 68.4% | 6.506 | +55,392 | -2,235 |
| 202511 | option_value_rule_select_hard | 57 | 68.4% | 6.473 | +55,064 | -2,235 |
| 202511 | option_value_best_select_hard | 57 | 57.9% | 5.041 | +59,536 | -2,742 |
| 202511 | option_value_best_select_learned_exit_5m | 57 | 56.1% | 3.902 | +43,683 | -2,742 |
| 202511 | oracle_best_delta_hard | 57 | 78.9% | 25.493 | +82,384 | -786 |
| 202511 | oracle_best_delta_oracle_exit | 57 | 100.0% | nan | +148,869 | +0 |
| 202512 | fixed_delta_0.70_hard | 65 | 63.1% | 2.901 | +19,346 | -1,924 |
| 202512 | fixed_delta_0.70_learned_exit_5m | 65 | 63.1% | 2.568 | +15,965 | -1,920 |
| 202512 | option_value_hold180_select_hard | 65 | 53.8% | 2.216 | +17,718 | -3,289 |
| 202512 | option_value_rule_select_hard | 65 | 55.4% | 2.180 | +17,599 | -3,289 |
| 202512 | option_value_best_select_hard | 65 | 33.8% | 1.243 | +5,837 | -4,579 |
| 202512 | option_value_best_select_learned_exit_5m | 65 | 33.8% | 1.040 | +978 | -6,954 |
| 202512 | oracle_best_delta_hard | 65 | 63.1% | 5.378 | +31,293 | -1,131 |
| 202512 | oracle_best_delta_oracle_exit | 65 | 92.3% | 221.440 | +67,838 | -112 |
| 202601 | fixed_delta_0.70_hard | 60 | 56.7% | 1.697 | +11,387 | -2,876 |
| 202601 | fixed_delta_0.70_learned_exit_5m | 60 | 56.7% | 1.511 | +8,346 | -2,876 |
| 202601 | option_value_hold180_select_hard | 60 | 41.7% | 1.446 | +9,257 | -3,897 |
| 202601 | option_value_rule_select_hard | 60 | 43.3% | 1.494 | +10,016 | -3,897 |
| 202601 | option_value_best_select_hard | 60 | 35.0% | 1.173 | +4,668 | -4,848 |
| 202601 | option_value_best_select_learned_exit_5m | 60 | 35.0% | 1.091 | +2,451 | -6,146 |
| 202601 | oracle_best_delta_hard | 60 | 56.7% | 4.272 | +29,641 | -1,149 |
| 202601 | oracle_best_delta_oracle_exit | 60 | 95.0% | 1934.127 | +99,862 | -25 |
| 202602 | fixed_delta_0.70_hard | 56 | 64.3% | 1.684 | +10,246 | -3,260 |
| 202602 | fixed_delta_0.70_learned_exit_5m | 56 | 64.3% | 1.666 | +9,972 | -3,260 |
| 202602 | option_value_hold180_select_hard | 56 | 58.9% | 1.458 | +8,021 | -3,260 |
| 202602 | option_value_rule_select_hard | 56 | 60.7% | 1.512 | +8,696 | -3,260 |
| 202602 | option_value_best_select_hard | 56 | 42.9% | 1.271 | +6,470 | -6,679 |
| 202602 | option_value_best_select_learned_exit_5m | 56 | 41.1% | 1.083 | +1,995 | -6,679 |
| 202602 | oracle_best_delta_hard | 56 | 64.3% | 5.069 | +32,013 | -1,174 |
| 202602 | oracle_best_delta_oracle_exit | 56 | 96.4% | 454.100 | +72,018 | -102 |
| 202603 | fixed_delta_0.70_hard | 66 | 63.6% | 5.173 | +45,325 | -5,546 |
| 202603 | fixed_delta_0.70_learned_exit_5m | 66 | 66.7% | 4.990 | +40,181 | -5,546 |
| 202603 | option_value_hold180_select_hard | 66 | 53.0% | 3.646 | +45,776 | -5,546 |
| 202603 | option_value_rule_select_hard | 66 | 54.5% | 3.701 | +46,587 | -5,546 |
| 202603 | option_value_best_select_hard | 66 | 45.5% | 2.840 | +40,017 | -5,908 |
| 202603 | option_value_best_select_learned_exit_5m | 66 | 48.5% | 2.671 | +35,024 | -5,908 |
| 202603 | oracle_best_delta_hard | 66 | 63.6% | 10.681 | +69,542 | -1,953 |
| 202603 | oracle_best_delta_oracle_exit | 66 | 95.5% | 1023.631 | +149,081 | -88 |
| 202604 | fixed_delta_0.70_hard | 52 | 59.6% | 2.002 | +13,449 | -3,548 |
| 202604 | fixed_delta_0.70_learned_exit_5m | 52 | 61.5% | 2.136 | +13,934 | -1,992 |
| 202604 | option_value_hold180_select_hard | 52 | 55.8% | 1.979 | +13,903 | -2,849 |
| 202604 | option_value_rule_select_hard | 52 | 57.7% | 1.913 | +12,731 | -2,849 |
| 202604 | option_value_best_select_hard | 52 | 44.2% | 1.656 | +13,359 | -4,429 |
| 202604 | option_value_best_select_learned_exit_5m | 52 | 46.2% | 1.798 | +15,325 | -3,400 |
| 202604 | oracle_best_delta_hard | 52 | 59.6% | 5.439 | +38,739 | -1,703 |
| 202604 | oracle_best_delta_oracle_exit | 52 | 80.8% | 87.592 | +94,580 | -342 |
| 202605 | fixed_delta_0.70_hard | 53 | 52.8% | 2.064 | +14,667 | -3,353 |
| 202605 | fixed_delta_0.70_learned_exit_5m | 53 | 54.7% | 2.009 | +13,498 | -3,353 |
| 202605 | option_value_hold180_select_hard | 53 | 47.2% | 1.748 | +12,524 | -3,353 |
| 202605 | option_value_rule_select_hard | 53 | 49.1% | 1.764 | +12,650 | -3,353 |
| 202605 | option_value_best_select_hard | 53 | 41.5% | 1.658 | +13,764 | -3,353 |
| 202605 | option_value_best_select_learned_exit_5m | 53 | 43.4% | 1.583 | +11,959 | -4,135 |
| 202605 | oracle_best_delta_hard | 53 | 52.8% | 4.653 | +30,741 | -1,303 |
| 202605 | oracle_best_delta_oracle_exit | 53 | 94.3% | 673.372 | +73,415 | -104 |

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
    "entry_batch_size": 1024,
    "dynamic_batch_size": 8192,
    "predict_batch_size": 4096,
    "max_dynamic_train_rows": 260000,
    "min_val_trades": 12,
    "seed": 7227,
    "device": "cuda",
    "log_every_epochs": 4
  },
  "candidate_rows": 19558,
  "state_rows": 704088,
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
    "202605"
  ],
  "market_feature_count": 222,
  "option_feature_count": 31,
  "dynamic_feature_count": 15,
  "policy_metrics": {
    "fixed_delta_0.70_hard": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.7428571428571429,
        "profit_factor": 5.760833750346658,
        "pnl_dollars": 1171609.5440362634,
        "max_drawdown": -5545.832033190643,
        "avg_pnl": 557.9093066839349,
        "avg_hold_minutes": 169.27380952380952,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.7027286666666667
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.7236467236467237,
          "profit_factor": 5.849070492778627,
          "pnl_dollars": 261821.11257482527,
          "max_drawdown": -2144.4928378222103,
          "avg_pnl": 372.9645478273864,
          "avg_hold_minutes": 170.3062678062678,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.7036631054131054
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7600574712643678,
          "profit_factor": 5.900544191257542,
          "pnl_dollars": 656430.5390873606,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 943.1473262749435,
          "avg_hold_minutes": 167.98850574712642,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.7008129310344827
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.7450142450142451,
          "profit_factor": 5.357066542993073,
          "pnl_dollars": 253357.89237407743,
          "max_drawdown": -2260.68503362051,
          "avg_pnl": 360.9086785955519,
          "avg_hold_minutes": 169.51566951566952,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.7036935897435896
        }
      }
    },
    "fixed_delta_0.70_learned_exit_5m": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.7509523809523809,
        "profit_factor": 5.398217253862389,
        "pnl_dollars": 1055623.0440362634,
        "max_drawdown": -5545.832033190527,
        "avg_pnl": 502.6776400172683,
        "avg_hold_minutes": 155.76666666666668,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.7027286666666667
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.7279202279202279,
          "profit_factor": 5.726837047986018,
          "pnl_dollars": 253035.11257482527,
          "max_drawdown": -2144.4928378222394,
          "avg_pnl": 360.4488783117169,
          "avg_hold_minutes": 162.8133903133903,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.7036631054131054
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7772988505747126,
          "profit_factor": 5.297083416663539,
          "pnl_dollars": 552895.5390873606,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 794.3901423668974,
          "avg_hold_minutes": 141.19971264367817,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.7008129310344827
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.7478632478632479,
          "profit_factor": 5.319014635465515,
          "pnl_dollars": 249692.39237407743,
          "max_drawdown": -1978.8314415110162,
          "avg_pnl": 355.68716862404193,
          "avg_hold_minutes": 163.16239316239316,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.7036935897435896
        }
      }
    },
    "option_value_hold180_select_hard": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.6576190476190477,
        "profit_factor": 4.414375486603303,
        "pnl_dollars": 1199158.9636399131,
        "max_drawdown": -5545.832033190643,
        "avg_pnl": 571.0280779237681,
        "avg_hold_minutes": 159.26904761904763,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.5715415714285714
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.6125356125356125,
          "profit_factor": 3.747811858830352,
          "pnl_dollars": 289914.1924850447,
          "max_drawdown": -3566.021427685686,
          "avg_pnl": 412.98318017812636,
          "avg_hold_minutes": 155.4985754985755,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.5306534188034189
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7155172413793104,
          "profit_factor": 5.198171915217671,
          "pnl_dollars": 611875.765441562,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 879.1318468987961,
          "avg_hold_minutes": 163.8433908045977,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.6500635057471265
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.6452991452991453,
          "profit_factor": 3.9750754189383115,
          "pnl_dollars": 297369.0057133065,
          "max_drawdown": -4145.5904854995315,
          "avg_pnl": 423.6025722411773,
          "avg_hold_minutes": 158.5042735042735,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.5345789173789174
        }
      }
    },
    "option_value_rule_select_hard": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.6595238095238095,
        "profit_factor": 4.414582096554419,
        "pnl_dollars": 1187153.7314328686,
        "max_drawdown": -5545.832033190643,
        "avg_pnl": 565.3113006823183,
        "avg_hold_minutes": 159.77380952380952,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.5777962380952382
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.6225071225071225,
          "profit_factor": 3.8391303030646293,
          "pnl_dollars": 286113.4785717716,
          "max_drawdown": -3253.238374669745,
          "avg_pnl": 407.56905779454644,
          "avg_hold_minutes": 157.22222222222223,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.543930341880342
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7083333333333334,
          "profit_factor": 5.049095769507623,
          "pnl_dollars": 603648.9704478511,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 867.3117391492113,
          "avg_hold_minutes": 163.18965517241378,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.6468063218390804
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.6481481481481481,
          "profit_factor": 4.040366329727714,
          "pnl_dollars": 297391.28241324605,
          "max_drawdown": -4207.8573136482155,
          "avg_pnl": 423.63430543197444,
          "avg_hold_minutes": 158.93874643874645,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.5432418803418804
        }
      }
    },
    "option_value_best_select_hard": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.518095238095238,
        "profit_factor": 2.9366660497347175,
        "pnl_dollars": 1106884.0944980765,
        "max_drawdown": -8179.565230882494,
        "avg_pnl": 527.0876640467031,
        "avg_hold_minutes": 143.2547619047619,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.3991945238095238
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.40883190883190884,
          "profit_factor": 2.1221605286966807,
          "pnl_dollars": 243558.2834615892,
          "max_drawdown": -9175.524458571745,
          "avg_pnl": 346.94912174015553,
          "avg_hold_minutes": 131.3960113960114,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.27760071225071226
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7068965517241379,
          "profit_factor": 5.083761643997209,
          "pnl_dollars": 629822.891973526,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 904.9179482378247,
          "avg_hold_minutes": 162.53591954022988,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.634644540229885
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.44017094017094016,
          "profit_factor": 2.1659359576121155,
          "pnl_dollars": 233502.91906296136,
          "max_drawdown": -7804.9569283312885,
          "avg_pnl": 332.6252408304293,
          "avg_hold_minutes": 135.997150997151,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.28735071225071224
        }
      }
    },
    "option_value_best_select_learned_exit_5m": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.5285714285714286,
        "profit_factor": 2.8285467852313184,
        "pnl_dollars": 1028827.0944980766,
        "max_drawdown": -8769.158124729409,
        "avg_pnl": 489.9176640467031,
        "avg_hold_minutes": 133.22857142857143,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.3991945238095238
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.42165242165242167,
          "profit_factor": 2.1591044885516286,
          "pnl_dollars": 249370.7834615892,
          "max_drawdown": -9585.524458571745,
          "avg_pnl": 355.2290362700701,
          "avg_hold_minutes": 128.56837606837607,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.27760071225071226
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7241379310344828,
          "profit_factor": 4.607642323317581,
          "pnl_dollars": 535872.891973526,
          "max_drawdown": -6007.752545622003,
          "avg_pnl": 769.9323160539167,
          "avg_hold_minutes": 137.76580459770116,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.634644540229885
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.4415954415954416,
          "profit_factor": 2.22423263339602,
          "pnl_dollars": 243583.4190629614,
          "max_drawdown": -10555.27913907211,
          "avg_pnl": 346.98492744011594,
          "avg_hold_minutes": 133.3903133903134,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.28735071225071224
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.7447619047619047,
        "profit_factor": 13.992741283958868,
        "pnl_dollars": 2084498.8640598669,
        "max_drawdown": -2092.563934390899,
        "avg_pnl": 992.6185066951747,
        "avg_hold_minutes": 155.11428571428573,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.5308664761904762
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.7250712250712251,
          "profit_factor": 12.945782358217025,
          "pnl_dollars": 618747.5152780514,
          "max_drawdown": -1703.3687367737293,
          "avg_pnl": 881.406716920301,
          "avg_hold_minutes": 156.11823361823363,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.5153074074074074
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7614942528735632,
          "profit_factor": 17.292907285644187,
          "pnl_dollars": 871219.1109468408,
          "max_drawdown": -1953.005264546373,
          "avg_pnl": 1251.7515961879897,
          "avg_hold_minutes": 152.65804597701148,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.5724577586206896
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.7478632478632479,
          "profit_factor": 11.77694666994226,
          "pnl_dollars": 594532.2378349747,
          "max_drawdown": -1978.831441511029,
          "avg_pnl": 846.9120197079411,
          "avg_hold_minutes": 156.54558404558404,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.5051897435897436
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.959047619047619,
        "profit_factor": 643.4321997615417,
        "pnl_dollars": 4256509.490043253,
        "max_drawdown": -342.42661216761917,
        "avg_pnl": 2026.9092809729775,
        "avg_hold_minutes": 114.56428571428572,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.3870815714285714
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.9629629629629629,
          "profit_factor": 627.70456503012,
          "pnl_dollars": 1384019.4451631005,
          "max_drawdown": -342.42661216761917,
          "avg_pnl": 1971.5376711725078,
          "avg_hold_minutes": 110.24216524216524,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.3255923076923077
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.9640804597701149,
          "profit_factor": 866.9894335595792,
          "pnl_dollars": 1626343.4533900311,
          "max_drawdown": -192.13284219556954,
          "avg_pnl": 2336.7003640661364,
          "avg_hold_minutes": 120.66091954022988,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.5069668103448276
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.9501424501424501,
          "profit_factor": 491.765226088318,
          "pnl_dollars": 1246146.591490121,
          "max_drawdown": -215.74634395036264,
          "avg_pnl": 1775.1375947152721,
          "avg_hold_minutes": 112.84188034188034,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.3297102564102565
        }
      }
    }
  }
}
```
