# OptionValueJEPA Walk-Forward Since 2022

Candidate labels: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\results\jepa_full_pipeline_option_policy\candidate_labels.parquet`
Train start: `20220801`
Min train months: `12`
Epochs per fold: `8`
Exit margin: `-0.3`

## Overall Walk-Forward Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 2102 | 74.3% | 5.770 | +1,173,822 | -5,546 | +558 | 169.3 | 0.703 |
| fixed_delta_0.70_learned_exit_5m | 2100 | 74.7% | 5.308 | +1,047,485 | -5,546 | +499 | 160.2 | 0.703 |
| option_value_hold180_select_hard | 2102 | 65.0% | 4.434 | +1,198,029 | -5,546 | +570 | 159.3 | 0.573 |
| option_value_rule_select_hard | 2102 | 65.9% | 4.520 | +1,197,018 | -5,546 | +569 | 160.0 | 0.581 |
| option_value_best_select_hard | 2102 | 51.6% | 2.875 | +1,086,233 | -9,198 | +517 | 143.4 | 0.401 |
| option_value_best_select_learned_exit_5m | 2100 | 52.1% | 2.810 | +1,019,088 | -8,447 | +485 | 137.7 | 0.400 |
| oracle_best_delta_hard | 2102 | 74.5% | 14.030 | +2,090,505 | -2,093 | +995 | 155.1 | 0.531 |
| oracle_best_delta_oracle_exit | 2102 | 95.9% | 644.962 | +4,266,645 | -342 | +2,030 | 114.6 | 0.387 |

## Fold Metrics

| Month | Policy | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202308 | fixed_delta_0.70_hard | 68 | 70.6% | 5.528 | +25,639 | -1,595 |
| 202308 | fixed_delta_0.70_learned_exit_5m | 68 | 70.6% | 5.632 | +27,052 | -1,867 |
| 202308 | option_value_hold180_select_hard | 68 | 67.6% | 4.120 | +26,140 | -1,946 |
| 202308 | option_value_rule_select_hard | 68 | 64.7% | 3.708 | +24,578 | -1,724 |
| 202308 | option_value_best_select_hard | 68 | 50.0% | 2.043 | +18,289 | -2,941 |
| 202308 | option_value_best_select_learned_exit_5m | 68 | 50.0% | 2.471 | +24,951 | -3,104 |
| 202308 | oracle_best_delta_hard | 68 | 70.6% | 11.697 | +49,152 | -1,034 |
| 202308 | oracle_best_delta_oracle_exit | 68 | 98.5% | 11085.873 | +101,623 | -9 |
| 202309 | fixed_delta_0.70_hard | 60 | 65.0% | 3.077 | +17,630 | -1,231 |
| 202309 | fixed_delta_0.70_learned_exit_5m | 60 | 66.7% | 3.596 | +20,623 | -1,182 |
| 202309 | option_value_hold180_select_hard | 60 | 56.7% | 2.922 | +20,728 | -2,023 |
| 202309 | option_value_rule_select_hard | 60 | 56.7% | 2.820 | +19,342 | -1,789 |
| 202309 | option_value_best_select_hard | 60 | 40.0% | 1.621 | +12,219 | -3,773 |
| 202309 | option_value_best_select_learned_exit_5m | 60 | 46.7% | 1.993 | +16,596 | -3,713 |
| 202309 | oracle_best_delta_hard | 60 | 65.0% | 6.722 | +36,610 | -1,207 |
| 202309 | oracle_best_delta_oracle_exit | 60 | 88.3% | 101.022 | +76,210 | -216 |
| 202310 | fixed_delta_0.70_hard | 66 | 66.7% | 4.174 | +40,067 | -5,122 |
| 202310 | fixed_delta_0.70_learned_exit_5m | 66 | 63.6% | 3.271 | +29,431 | -5,122 |
| 202310 | option_value_hold180_select_hard | 66 | 60.6% | 3.835 | +43,810 | -5,122 |
| 202310 | option_value_rule_select_hard | 66 | 63.6% | 3.882 | +43,416 | -5,244 |
| 202310 | option_value_best_select_hard | 66 | 51.5% | 3.330 | +49,532 | -6,294 |
| 202310 | option_value_best_select_learned_exit_5m | 66 | 45.5% | 2.473 | +33,136 | -6,493 |
| 202310 | oracle_best_delta_hard | 66 | 66.7% | 10.369 | +76,602 | -1,979 |
| 202310 | oracle_best_delta_oracle_exit | 66 | 90.9% | 890.445 | +177,524 | -134 |
| 202311 | fixed_delta_0.70_hard | 63 | 74.6% | 5.868 | +25,741 | -851 |
| 202311 | fixed_delta_0.70_learned_exit_5m | 63 | 77.8% | 6.266 | +26,068 | -814 |
| 202311 | option_value_hold180_select_hard | 63 | 65.1% | 4.195 | +23,853 | -1,223 |
| 202311 | option_value_rule_select_hard | 63 | 65.1% | 4.206 | +24,021 | -1,223 |
| 202311 | option_value_best_select_hard | 63 | 54.0% | 2.722 | +25,437 | -2,293 |
| 202311 | option_value_best_select_learned_exit_5m | 63 | 54.0% | 2.623 | +22,342 | -2,120 |
| 202311 | oracle_best_delta_hard | 63 | 74.6% | 10.519 | +47,433 | -851 |
| 202311 | oracle_best_delta_oracle_exit | 63 | 95.2% | 385.207 | +115,398 | -123 |
| 202312 | fixed_delta_0.70_hard | 59 | 83.1% | 8.141 | +25,379 | -1,002 |
| 202312 | fixed_delta_0.70_learned_exit_5m | 59 | 79.7% | 6.015 | +24,171 | -1,002 |
| 202312 | option_value_hold180_select_hard | 59 | 67.8% | 3.154 | +18,763 | -1,080 |
| 202312 | option_value_rule_select_hard | 59 | 69.5% | 3.317 | +19,571 | -1,344 |
| 202312 | option_value_best_select_hard | 59 | 54.2% | 2.209 | +16,306 | -3,122 |
| 202312 | option_value_best_select_learned_exit_5m | 59 | 49.2% | 2.309 | +18,377 | -2,745 |
| 202312 | oracle_best_delta_hard | 59 | 83.1% | 19.268 | +49,736 | -629 |
| 202312 | oracle_best_delta_oracle_exit | 59 | 100.0% | nan | +83,091 | +0 |
| 202401 | fixed_delta_0.70_hard | 63 | 84.1% | 13.838 | +45,294 | -824 |
| 202401 | fixed_delta_0.70_learned_exit_5m | 63 | 87.3% | 21.346 | +46,029 | -663 |
| 202401 | option_value_hold180_select_hard | 63 | 81.0% | 15.222 | +56,329 | -824 |
| 202401 | option_value_rule_select_hard | 63 | 81.0% | 15.260 | +55,222 | -824 |
| 202401 | option_value_best_select_hard | 63 | 66.7% | 6.773 | +58,559 | -1,360 |
| 202401 | option_value_best_select_learned_exit_5m | 63 | 71.4% | 9.004 | +63,519 | -1,338 |
| 202401 | oracle_best_delta_hard | 63 | 84.1% | 30.375 | +90,726 | -629 |
| 202401 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +153,426 | +0 |
| 202402 | fixed_delta_0.70_hard | 60 | 81.7% | 10.974 | +37,684 | -863 |
| 202402 | fixed_delta_0.70_learned_exit_5m | 60 | 81.7% | 10.311 | +35,179 | -863 |
| 202402 | option_value_hold180_select_hard | 60 | 80.0% | 9.893 | +43,116 | -992 |
| 202402 | option_value_rule_select_hard | 60 | 80.0% | 8.589 | +41,496 | -992 |
| 202402 | option_value_best_select_hard | 60 | 58.3% | 3.997 | +37,291 | -2,584 |
| 202402 | option_value_best_select_learned_exit_5m | 60 | 56.7% | 3.697 | +33,416 | -2,150 |
| 202402 | oracle_best_delta_hard | 60 | 81.7% | 22.205 | +72,395 | -863 |
| 202402 | oracle_best_delta_oracle_exit | 60 | 96.7% | 409.816 | +116,332 | -144 |
| 202403 | fixed_delta_0.70_hard | 60 | 81.7% | 5.501 | +19,681 | -1,631 |
| 202403 | fixed_delta_0.70_learned_exit_5m | 60 | 78.3% | 4.859 | +17,779 | -1,631 |
| 202403 | option_value_hold180_select_hard | 60 | 78.3% | 6.473 | +23,826 | -1,018 |
| 202403 | option_value_rule_select_hard | 60 | 76.7% | 5.398 | +23,592 | -1,722 |
| 202403 | option_value_best_select_hard | 60 | 48.3% | 2.032 | +14,160 | -2,856 |
| 202403 | option_value_best_select_learned_exit_5m | 60 | 50.0% | 1.971 | +13,280 | -3,021 |
| 202403 | oracle_best_delta_hard | 60 | 81.7% | 12.503 | +38,518 | -993 |
| 202403 | oracle_best_delta_oracle_exit | 60 | 93.3% | 386.165 | +92,858 | -110 |
| 202404 | fixed_delta_0.70_hard | 65 | 72.3% | 6.892 | +43,237 | -2,086 |
| 202404 | fixed_delta_0.70_learned_exit_5m | 65 | 75.4% | 5.654 | +33,058 | -2,086 |
| 202404 | option_value_hold180_select_hard | 65 | 55.4% | 5.102 | +44,431 | -2,687 |
| 202404 | option_value_rule_select_hard | 65 | 56.9% | 5.101 | +43,925 | -2,633 |
| 202404 | option_value_best_select_hard | 65 | 44.6% | 2.472 | +30,311 | -4,821 |
| 202404 | option_value_best_select_learned_exit_5m | 65 | 47.7% | 2.640 | +31,590 | -4,821 |
| 202404 | oracle_best_delta_hard | 65 | 72.3% | 15.123 | +68,389 | -1,136 |
| 202404 | oracle_best_delta_oracle_exit | 65 | 96.9% | 1186.668 | +234,674 | -116 |
| 202405 | fixed_delta_0.70_hard | 66 | 69.7% | 6.275 | +28,378 | -1,483 |
| 202405 | fixed_delta_0.70_learned_exit_5m | 66 | 69.7% | 5.950 | +26,631 | -1,483 |
| 202405 | option_value_hold180_select_hard | 66 | 59.1% | 3.916 | +27,838 | -2,007 |
| 202405 | option_value_rule_select_hard | 66 | 57.6% | 3.587 | +24,440 | -2,007 |
| 202405 | option_value_best_select_hard | 66 | 56.1% | 2.422 | +21,294 | -3,162 |
| 202405 | option_value_best_select_learned_exit_5m | 66 | 54.5% | 2.640 | +24,345 | -3,162 |
| 202405 | oracle_best_delta_hard | 66 | 69.7% | 9.505 | +41,173 | -1,093 |
| 202405 | oracle_best_delta_oracle_exit | 66 | 92.4% | 401.349 | +98,201 | -179 |
| 202406 | fixed_delta_0.70_hard | 57 | 78.9% | 6.928 | +27,668 | -875 |
| 202406 | fixed_delta_0.70_learned_exit_5m | 57 | 78.9% | 6.584 | +26,061 | -875 |
| 202406 | option_value_hold180_select_hard | 57 | 70.2% | 6.826 | +38,437 | -1,819 |
| 202406 | option_value_rule_select_hard | 57 | 73.7% | 7.671 | +39,740 | -1,179 |
| 202406 | option_value_best_select_hard | 57 | 57.9% | 3.791 | +32,484 | -2,587 |
| 202406 | option_value_best_select_learned_exit_5m | 57 | 56.1% | 3.251 | +28,414 | -2,587 |
| 202406 | oracle_best_delta_hard | 57 | 78.9% | 16.234 | +56,199 | -744 |
| 202406 | oracle_best_delta_oracle_exit | 57 | 100.0% | nan | +183,763 | +0 |
| 202407 | fixed_delta_0.70_hard | 66 | 77.3% | 3.565 | +23,801 | -4,455 |
| 202407 | fixed_delta_0.70_learned_exit_5m | 66 | 77.3% | 4.043 | +28,231 | -3,381 |
| 202407 | option_value_hold180_select_hard | 66 | 63.6% | 3.100 | +25,581 | -4,455 |
| 202407 | option_value_rule_select_hard | 66 | 65.2% | 3.185 | +25,929 | -4,653 |
| 202407 | option_value_best_select_hard | 66 | 43.9% | 1.885 | +19,718 | -4,884 |
| 202407 | option_value_best_select_learned_exit_5m | 66 | 42.4% | 2.242 | +26,927 | -3,381 |
| 202407 | oracle_best_delta_hard | 66 | 77.3% | 11.805 | +60,756 | -969 |
| 202407 | oracle_best_delta_oracle_exit | 66 | 95.5% | 315.692 | +115,699 | -156 |
| 202408 | fixed_delta_0.70_hard | 66 | 74.2% | 5.486 | +36,091 | -3,233 |
| 202408 | fixed_delta_0.70_learned_exit_5m | 66 | 77.3% | 4.930 | +28,079 | -3,233 |
| 202408 | option_value_hold180_select_hard | 66 | 60.6% | 2.785 | +26,104 | -3,798 |
| 202408 | option_value_rule_select_hard | 66 | 63.6% | 2.902 | +26,154 | -3,798 |
| 202408 | option_value_best_select_hard | 66 | 50.0% | 2.345 | +28,407 | -3,727 |
| 202408 | option_value_best_select_learned_exit_5m | 66 | 53.0% | 2.143 | +22,877 | -3,727 |
| 202408 | oracle_best_delta_hard | 66 | 74.2% | 12.736 | +55,881 | -900 |
| 202408 | oracle_best_delta_oracle_exit | 66 | 92.4% | 342.088 | +118,528 | -138 |
| 202409 | fixed_delta_0.70_hard | 60 | 83.3% | 22.453 | +43,979 | -685 |
| 202409 | fixed_delta_0.70_learned_exit_5m | 60 | 83.3% | 19.985 | +38,919 | -685 |
| 202409 | option_value_hold180_select_hard | 60 | 73.3% | 7.763 | +42,832 | -1,013 |
| 202409 | option_value_rule_select_hard | 60 | 73.3% | 7.554 | +41,769 | -1,013 |
| 202409 | option_value_best_select_hard | 60 | 55.0% | 3.271 | +35,514 | -4,115 |
| 202409 | option_value_best_select_learned_exit_5m | 60 | 55.0% | 2.917 | +28,523 | -4,859 |
| 202409 | oracle_best_delta_hard | 60 | 83.3% | 39.038 | +71,261 | -584 |
| 202409 | oracle_best_delta_oracle_exit | 60 | 98.3% | 20599.806 | +141,809 | -7 |
| 202410 | fixed_delta_0.70_hard | 69 | 81.2% | 14.039 | +39,042 | -925 |
| 202410 | fixed_delta_0.70_learned_exit_5m | 69 | 81.2% | 14.273 | +39,744 | -925 |
| 202410 | option_value_hold180_select_hard | 69 | 65.2% | 4.327 | +32,064 | -2,051 |
| 202410 | option_value_rule_select_hard | 69 | 68.1% | 5.473 | +36,029 | -2,051 |
| 202410 | option_value_best_select_hard | 69 | 49.3% | 2.940 | +30,561 | -4,550 |
| 202410 | option_value_best_select_learned_exit_5m | 69 | 50.7% | 3.419 | +37,419 | -4,550 |
| 202410 | oracle_best_delta_hard | 69 | 81.2% | 29.954 | +62,684 | -452 |
| 202410 | oracle_best_delta_oracle_exit | 69 | 97.1% | 2965.577 | +115,797 | -24 |
| 202411 | fixed_delta_0.70_hard | 60 | 68.3% | 4.547 | +25,702 | -2,092 |
| 202411 | fixed_delta_0.70_learned_exit_5m | 60 | 66.7% | 4.672 | +28,413 | -2,092 |
| 202411 | option_value_hold180_select_hard | 60 | 63.3% | 5.094 | +31,204 | -1,246 |
| 202411 | option_value_rule_select_hard | 60 | 65.0% | 5.271 | +30,693 | -1,317 |
| 202411 | option_value_best_select_hard | 60 | 55.0% | 3.653 | +38,805 | -2,092 |
| 202411 | option_value_best_select_learned_exit_5m | 60 | 53.3% | 3.451 | +36,231 | -2,877 |
| 202411 | oracle_best_delta_hard | 60 | 70.0% | 14.827 | +75,311 | -1,206 |
| 202411 | oracle_best_delta_oracle_exit | 60 | 98.3% | 580.346 | +108,296 | -187 |
| 202412 | fixed_delta_0.70_hard | 62 | 82.3% | 6.313 | +27,375 | -996 |
| 202412 | fixed_delta_0.70_learned_exit_5m | 62 | 85.5% | 8.723 | +35,907 | -969 |
| 202412 | option_value_hold180_select_hard | 62 | 67.7% | 3.377 | +23,090 | -1,378 |
| 202412 | option_value_rule_select_hard | 62 | 67.7% | 3.423 | +22,175 | -1,478 |
| 202412 | option_value_best_select_hard | 62 | 51.6% | 2.213 | +17,067 | -1,780 |
| 202412 | option_value_best_select_learned_exit_5m | 62 | 50.0% | 2.294 | +20,280 | -4,113 |
| 202412 | oracle_best_delta_hard | 62 | 82.3% | 13.871 | +54,657 | -889 |
| 202412 | oracle_best_delta_oracle_exit | 62 | 98.4% | 1660.548 | +91,034 | -55 |
| 202501 | fixed_delta_0.70_hard | 60 | 75.0% | 8.019 | +47,721 | -1,655 |
| 202501 | fixed_delta_0.70_learned_exit_5m | 60 | 75.0% | 6.971 | +40,597 | -1,655 |
| 202501 | option_value_hold180_select_hard | 60 | 68.3% | 5.973 | +48,118 | -1,655 |
| 202501 | option_value_rule_select_hard | 60 | 68.3% | 6.229 | +48,348 | -1,655 |
| 202501 | option_value_best_select_hard | 60 | 56.7% | 4.043 | +50,460 | -5,541 |
| 202501 | option_value_best_select_learned_exit_5m | 60 | 56.7% | 3.634 | +43,703 | -4,946 |
| 202501 | oracle_best_delta_hard | 60 | 76.7% | 23.465 | +88,626 | -580 |
| 202501 | oracle_best_delta_oracle_exit | 60 | 96.7% | 382.901 | +152,963 | -208 |
| 202502 | fixed_delta_0.70_hard | 57 | 80.7% | 6.955 | +35,658 | -2,216 |
| 202502 | fixed_delta_0.70_learned_exit_5m | 57 | 80.7% | 6.766 | +34,524 | -2,216 |
| 202502 | option_value_hold180_select_hard | 57 | 64.9% | 4.420 | +35,822 | -3,398 |
| 202502 | option_value_rule_select_hard | 57 | 63.2% | 4.137 | +35,183 | -3,398 |
| 202502 | option_value_best_select_hard | 57 | 49.1% | 2.723 | +30,190 | -4,589 |
| 202502 | option_value_best_select_learned_exit_5m | 57 | 49.1% | 3.056 | +36,042 | -2,486 |
| 202502 | oracle_best_delta_hard | 57 | 80.7% | 17.040 | +57,820 | -600 |
| 202502 | oracle_best_delta_oracle_exit | 57 | 96.5% | 1151.387 | +151,151 | -74 |
| 202503 | fixed_delta_0.70_hard | 63 | 87.3% | 12.883 | +78,898 | -3,148 |
| 202503 | fixed_delta_0.70_learned_exit_5m | 63 | 87.3% | 10.098 | +60,405 | -3,148 |
| 202503 | option_value_hold180_select_hard | 63 | 77.8% | 11.509 | +85,799 | -3,148 |
| 202503 | option_value_rule_select_hard | 63 | 77.8% | 11.639 | +86,867 | -3,148 |
| 202503 | option_value_best_select_hard | 63 | 65.1% | 7.567 | +83,891 | -3,664 |
| 202503 | option_value_best_select_learned_exit_5m | 63 | 68.3% | 6.186 | +66,702 | -3,664 |
| 202503 | oracle_best_delta_hard | 63 | 87.3% | 37.693 | +114,485 | -472 |
| 202503 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +180,300 | +0 |
| 202504 | fixed_delta_0.70_hard | 60 | 81.7% | 6.746 | +92,791 | -5,032 |
| 202504 | fixed_delta_0.70_learned_exit_5m | 60 | 80.0% | 3.662 | +43,833 | -5,032 |
| 202504 | option_value_hold180_select_hard | 60 | 73.3% | 6.702 | +99,509 | -5,032 |
| 202504 | option_value_rule_select_hard | 60 | 73.3% | 6.703 | +99,537 | -5,032 |
| 202504 | option_value_best_select_hard | 60 | 61.7% | 5.731 | +98,196 | -5,032 |
| 202504 | option_value_best_select_learned_exit_5m | 60 | 56.7% | 3.669 | +56,853 | -5,032 |
| 202504 | oracle_best_delta_hard | 60 | 85.0% | 37.361 | +137,443 | -570 |
| 202504 | oracle_best_delta_oracle_exit | 60 | 93.3% | 588.020 | +249,111 | -168 |
| 202505 | fixed_delta_0.70_hard | 63 | 74.6% | 7.812 | +35,841 | -1,725 |
| 202505 | fixed_delta_0.70_learned_exit_5m | 63 | 76.2% | 9.423 | +41,636 | -1,725 |
| 202505 | option_value_hold180_select_hard | 63 | 63.5% | 5.057 | +33,330 | -1,725 |
| 202505 | option_value_rule_select_hard | 63 | 66.7% | 5.885 | +33,856 | -1,725 |
| 202505 | option_value_best_select_hard | 63 | 49.2% | 3.274 | +33,306 | -3,140 |
| 202505 | option_value_best_select_learned_exit_5m | 63 | 50.8% | 4.006 | +43,675 | -2,164 |
| 202505 | oracle_best_delta_hard | 63 | 74.6% | 22.747 | +71,426 | -645 |
| 202505 | oracle_best_delta_oracle_exit | 63 | 98.4% | 2535.697 | +149,233 | -59 |
| 202506 | fixed_delta_0.70_hard | 60 | 73.3% | 7.107 | +33,027 | -1,753 |
| 202506 | fixed_delta_0.70_learned_exit_5m | 60 | 75.0% | 7.252 | +31,090 | -1,753 |
| 202506 | option_value_hold180_select_hard | 60 | 65.0% | 4.613 | +35,316 | -1,965 |
| 202506 | option_value_rule_select_hard | 60 | 65.0% | 4.829 | +36,300 | -1,924 |
| 202506 | option_value_best_select_hard | 60 | 45.0% | 2.666 | +28,502 | -2,355 |
| 202506 | option_value_best_select_learned_exit_5m | 60 | 48.3% | 2.890 | +28,519 | -1,989 |
| 202506 | oracle_best_delta_hard | 60 | 73.3% | 13.814 | +53,346 | -958 |
| 202506 | oracle_best_delta_oracle_exit | 60 | 95.0% | 1927.640 | +98,648 | -24 |
| 202507 | fixed_delta_0.70_hard | 66 | 78.8% | 7.445 | +28,097 | -1,418 |
| 202507 | fixed_delta_0.70_learned_exit_5m | 66 | 77.3% | 6.294 | +26,290 | -1,418 |
| 202507 | option_value_hold180_select_hard | 66 | 71.2% | 4.793 | +25,254 | -911 |
| 202507 | option_value_rule_select_hard | 66 | 69.7% | 4.435 | +23,802 | -764 |
| 202507 | option_value_best_select_hard | 66 | 59.1% | 2.443 | +19,670 | -1,972 |
| 202507 | option_value_best_select_learned_exit_5m | 66 | 54.5% | 2.387 | +18,980 | -1,972 |
| 202507 | oracle_best_delta_hard | 66 | 78.8% | 12.612 | +38,440 | -566 |
| 202507 | oracle_best_delta_oracle_exit | 66 | 98.5% | 707.565 | +83,050 | -118 |
| 202508 | fixed_delta_0.70_hard | 63 | 68.3% | 4.155 | +19,624 | -950 |
| 202508 | fixed_delta_0.70_learned_exit_5m | 63 | 71.4% | 4.918 | +20,424 | -950 |
| 202508 | option_value_hold180_select_hard | 63 | 60.3% | 2.554 | +14,870 | -1,692 |
| 202508 | option_value_rule_select_hard | 63 | 61.9% | 2.814 | +15,632 | -1,316 |
| 202508 | option_value_best_select_hard | 63 | 47.6% | 1.400 | +7,020 | -5,124 |
| 202508 | option_value_best_select_learned_exit_5m | 63 | 50.8% | 1.547 | +9,009 | -4,628 |
| 202508 | oracle_best_delta_hard | 63 | 68.3% | 5.994 | +27,185 | -640 |
| 202508 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +60,602 | +0 |
| 202509 | fixed_delta_0.70_hard | 62 | 77.4% | 13.267 | +36,057 | -781 |
| 202509 | fixed_delta_0.70_learned_exit_5m | 62 | 77.4% | 13.593 | +37,013 | -781 |
| 202509 | option_value_hold180_select_hard | 62 | 72.6% | 10.151 | +40,266 | -1,216 |
| 202509 | option_value_rule_select_hard | 62 | 72.6% | 10.147 | +40,441 | -1,216 |
| 202509 | option_value_best_select_hard | 62 | 61.3% | 3.816 | +34,907 | -3,185 |
| 202509 | option_value_best_select_learned_exit_5m | 62 | 64.5% | 4.795 | +42,574 | -2,272 |
| 202509 | oracle_best_delta_hard | 62 | 77.4% | 20.799 | +56,066 | -717 |
| 202509 | oracle_best_delta_oracle_exit | 62 | 96.8% | 559.154 | +104,486 | -99 |
| 202510 | fixed_delta_0.70_hard | 67 | 89.6% | 29.078 | +63,291 | -1,667 |
| 202510 | fixed_delta_0.70_learned_exit_5m | 67 | 86.6% | 22.160 | +53,424 | -1,791 |
| 202510 | option_value_hold180_select_hard | 67 | 82.1% | 18.755 | +67,395 | -1,667 |
| 202510 | option_value_rule_select_hard | 67 | 86.6% | 22.181 | +67,980 | -1,667 |
| 202510 | option_value_best_select_hard | 67 | 77.6% | 12.983 | +81,354 | -1,667 |
| 202510 | option_value_best_select_learned_exit_5m | 67 | 74.6% | 11.727 | +76,614 | -1,791 |
| 202510 | oracle_best_delta_hard | 67 | 89.6% | 122.060 | +117,825 | -386 |
| 202510 | oracle_best_delta_oracle_exit | 67 | 97.0% | 1349.134 | +197,040 | -78 |
| 202511 | fixed_delta_0.70_hard | 57 | 78.9% | 11.588 | +53,797 | -2,235 |
| 202511 | fixed_delta_0.70_learned_exit_5m | 57 | 80.7% | 7.477 | +41,756 | -1,985 |
| 202511 | option_value_hold180_select_hard | 57 | 68.4% | 6.463 | +56,153 | -2,235 |
| 202511 | option_value_rule_select_hard | 57 | 70.2% | 6.481 | +55,385 | -2,235 |
| 202511 | option_value_best_select_hard | 57 | 52.6% | 4.419 | +55,045 | -2,742 |
| 202511 | option_value_best_select_learned_exit_5m | 57 | 59.6% | 4.063 | +45,877 | -2,742 |
| 202511 | oracle_best_delta_hard | 57 | 78.9% | 25.493 | +82,384 | -786 |
| 202511 | oracle_best_delta_oracle_exit | 57 | 100.0% | nan | +148,869 | +0 |
| 202512 | fixed_delta_0.70_hard | 65 | 63.1% | 2.901 | +19,346 | -1,924 |
| 202512 | fixed_delta_0.70_learned_exit_5m | 65 | 64.6% | 2.892 | +19,788 | -2,608 |
| 202512 | option_value_hold180_select_hard | 65 | 56.9% | 2.274 | +16,779 | -3,016 |
| 202512 | option_value_rule_select_hard | 65 | 58.5% | 2.338 | +17,554 | -3,533 |
| 202512 | option_value_best_select_hard | 65 | 36.9% | 1.314 | +7,389 | -4,150 |
| 202512 | option_value_best_select_learned_exit_5m | 65 | 36.9% | 1.312 | +7,468 | -4,550 |
| 202512 | oracle_best_delta_hard | 65 | 63.1% | 5.378 | +31,293 | -1,131 |
| 202512 | oracle_best_delta_oracle_exit | 65 | 92.3% | 221.440 | +67,838 | -112 |
| 202601 | fixed_delta_0.70_hard | 60 | 56.7% | 1.697 | +11,387 | -2,876 |
| 202601 | fixed_delta_0.70_learned_exit_5m | 60 | 60.0% | 1.986 | +13,809 | -2,876 |
| 202601 | option_value_hold180_select_hard | 60 | 41.7% | 1.528 | +11,208 | -3,713 |
| 202601 | option_value_rule_select_hard | 60 | 43.3% | 1.595 | +12,048 | -3,713 |
| 202601 | option_value_best_select_hard | 60 | 33.3% | 1.109 | +3,032 | -5,455 |
| 202601 | option_value_best_select_learned_exit_5m | 60 | 40.0% | 1.691 | +15,854 | -4,417 |
| 202601 | oracle_best_delta_hard | 60 | 56.7% | 4.272 | +29,641 | -1,149 |
| 202601 | oracle_best_delta_oracle_exit | 60 | 95.0% | 1934.127 | +99,862 | -25 |
| 202602 | fixed_delta_0.70_hard | 56 | 64.3% | 1.684 | +10,246 | -3,260 |
| 202602 | fixed_delta_0.70_learned_exit_5m | 56 | 64.3% | 1.716 | +10,719 | -3,260 |
| 202602 | option_value_hold180_select_hard | 56 | 53.6% | 1.428 | +8,170 | -3,603 |
| 202602 | option_value_rule_select_hard | 56 | 55.4% | 1.387 | +7,043 | -3,260 |
| 202602 | option_value_best_select_hard | 56 | 42.9% | 1.236 | +5,716 | -6,744 |
| 202602 | option_value_best_select_learned_exit_5m | 56 | 41.1% | 0.891 | -2,657 | -7,546 |
| 202602 | oracle_best_delta_hard | 56 | 64.3% | 5.069 | +32,013 | -1,174 |
| 202602 | oracle_best_delta_oracle_exit | 56 | 96.4% | 454.100 | +72,018 | -102 |
| 202603 | fixed_delta_0.70_hard | 66 | 63.6% | 5.173 | +45,325 | -5,546 |
| 202603 | fixed_delta_0.70_learned_exit_5m | 66 | 62.1% | 4.176 | +34,832 | -5,546 |
| 202603 | option_value_hold180_select_hard | 66 | 50.0% | 3.757 | +46,447 | -5,546 |
| 202603 | option_value_rule_select_hard | 66 | 51.5% | 4.007 | +48,469 | -5,546 |
| 202603 | option_value_best_select_hard | 66 | 40.9% | 2.768 | +37,832 | -6,055 |
| 202603 | option_value_best_select_learned_exit_5m | 66 | 43.9% | 2.360 | +30,041 | -6,176 |
| 202603 | oracle_best_delta_hard | 66 | 63.6% | 10.681 | +69,542 | -1,953 |
| 202603 | oracle_best_delta_oracle_exit | 66 | 95.5% | 1023.631 | +149,081 | -88 |
| 202604 | fixed_delta_0.70_hard | 52 | 59.6% | 2.002 | +13,449 | -3,548 |
| 202604 | fixed_delta_0.70_learned_exit_5m | 52 | 61.5% | 2.031 | +13,743 | -3,548 |
| 202604 | option_value_hold180_select_hard | 52 | 51.9% | 1.611 | +8,788 | -2,890 |
| 202604 | option_value_rule_select_hard | 52 | 51.9% | 1.654 | +9,346 | -2,890 |
| 202604 | option_value_best_select_hard | 52 | 42.3% | 1.424 | +8,650 | -4,423 |
| 202604 | option_value_best_select_learned_exit_5m | 52 | 44.2% | 1.408 | +8,202 | -4,423 |
| 202604 | oracle_best_delta_hard | 52 | 59.6% | 5.439 | +38,739 | -1,703 |
| 202604 | oracle_best_delta_oracle_exit | 52 | 80.8% | 87.592 | +94,580 | -342 |
| 202605 | fixed_delta_0.70_hard | 53 | 52.8% | 2.064 | +14,667 | -3,353 |
| 202605 | fixed_delta_0.70_learned_exit_5m | 52 | 53.8% | 1.815 | +10,907 | -3,353 |
| 202605 | option_value_hold180_select_hard | 53 | 49.1% | 1.988 | +14,446 | -2,467 |
| 202605 | option_value_rule_select_hard | 53 | 50.9% | 2.034 | +14,921 | -2,467 |
| 202605 | option_value_best_select_hard | 53 | 39.6% | 1.511 | +11,381 | -3,367 |
| 202605 | option_value_best_select_learned_exit_5m | 52 | 42.3% | 1.408 | +8,574 | -5,646 |
| 202605 | oracle_best_delta_hard | 53 | 52.8% | 4.653 | +30,741 | -1,303 |
| 202605 | oracle_best_delta_oracle_exit | 53 | 94.3% | 673.372 | +73,415 | -104 |
| 202606 | fixed_delta_0.70_hard | 2 | 100.0% | nan | +2,213 | +0 |
| 202606 | fixed_delta_0.70_learned_exit_5m | 1 | 100.0% | nan | +1,320 | +0 |
| 202606 | option_value_hold180_select_hard | 2 | 100.0% | nan | +2,213 | +0 |
| 202606 | option_value_rule_select_hard | 2 | 100.0% | nan | +2,213 | +0 |
| 202606 | option_value_best_select_hard | 2 | 100.0% | nan | +3,740 | +0 |
| 202606 | option_value_best_select_learned_exit_5m | 1 | 100.0% | nan | +836 | +0 |
| 202606 | oracle_best_delta_hard | 2 | 100.0% | nan | +6,006 | +0 |
| 202606 | oracle_best_delta_oracle_exit | 2 | 100.0% | nan | +10,135 | +0 |

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
  "candidate_rows": 19572,
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
    "202605",
    "202606"
  ],
  "market_feature_count": 222,
  "option_feature_count": 31,
  "dynamic_feature_count": 15,
  "policy_metrics": {
    "fixed_delta_0.70_hard": {
      "overall": {
        "trades": 2102,
        "win_rate": 0.7431018078020932,
        "profit_factor": 5.769825111887234,
        "pnl_dollars": 1173822.2583521227,
        "max_drawdown": -5545.832033190643,
        "avg_pnl": 558.4311409857862,
        "avg_hold_minutes": 169.28401522359658,
        "long_rate": 0.5499524262607041,
        "avg_delta_abs": 0.7027223596574691
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.7240398293029872,
          "profit_factor": 5.872873573339753,
          "pnl_dollars": 263106.33807206305,
          "max_drawdown": -2144.4928378222103,
          "avg_pnl": 374.2622163187241,
          "avg_hold_minutes": 170.32005689900427,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.7035975817923186
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
          "trades": 703,
          "win_rate": 0.7453769559032717,
          "profit_factor": 5.3730168276388355,
          "pnl_dollars": 254285.3811926991,
          "max_drawdown": -2260.68503362051,
          "avg_pnl": 361.71462474068153,
          "avg_hold_minutes": 169.53058321479375,
          "long_rate": 0.5448079658605974,
          "avg_delta_abs": 0.7037375533428164
        }
      }
    },
    "fixed_delta_0.70_learned_exit_5m": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.7471428571428571,
        "profit_factor": 5.307539547526844,
        "pnl_dollars": 1047484.6544676109,
        "max_drawdown": -5545.832033190527,
        "avg_pnl": 498.802216413148,
        "avg_hold_minutes": 160.21666666666667,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.7026884285714285
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.7254623044096729,
          "profit_factor": 5.797784732515442,
          "pnl_dollars": 257299.8750541322,
          "max_drawdown": -2144.4928378222394,
          "avg_pnl": 366.00266721782674,
          "avg_hold_minutes": 166.90611664295875,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.7035975817923186
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.771551724137931,
          "profit_factor": 5.120234276108435,
          "pnl_dollars": 541386.7586494494,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 777.8545382894389,
          "avg_hold_minutes": 146.6594827586207,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.7008129310344827
        },
        "SPY": {
          "trades": 701,
          "win_rate": 0.7446504992867332,
          "profit_factor": 5.278649155453589,
          "pnl_dollars": 248798.02076402918,
          "max_drawdown": -2260.68503362051,
          "avg_pnl": 354.91871720974206,
          "avg_hold_minutes": 166.96861626248216,
          "long_rate": 0.543509272467903,
          "avg_delta_abs": 0.7036388017118402
        }
      }
    },
    "option_value_hold180_select_hard": {
      "overall": {
        "trades": 2102,
        "win_rate": 0.6503330161750713,
        "profit_factor": 4.434211773874333,
        "pnl_dollars": 1198028.7461745082,
        "max_drawdown": -5545.832033190643,
        "avg_pnl": 569.9470723951039,
        "avg_hold_minutes": 159.2697431018078,
        "long_rate": 0.5499524262607041,
        "avg_delta_abs": 0.5732310656517603
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.5988620199146515,
          "profit_factor": 3.763569093739414,
          "pnl_dollars": 291592.5884417166,
          "max_drawdown": -4759.275562048424,
          "avg_pnl": 414.78319835237073,
          "avg_hold_minutes": 155.8321479374111,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.5305735419630156
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7126436781609196,
          "profit_factor": 5.238765046562865,
          "pnl_dollars": 608459.6145150174,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 874.2235840733008,
          "avg_hold_minutes": 163.18965517241378,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.6517837643678162
        },
        "SPY": {
          "trades": 703,
          "win_rate": 0.6401137980085349,
          "profit_factor": 3.985985971728242,
          "pnl_dollars": 297976.5432177742,
          "max_drawdown": -3639.602974960173,
          "avg_pnl": 423.8642151035195,
          "avg_hold_minutes": 158.82645803698435,
          "long_rate": 0.5448079658605974,
          "avg_delta_abs": 0.538118065433855
        }
      }
    },
    "option_value_rule_select_hard": {
      "overall": {
        "trades": 2102,
        "win_rate": 0.6588962892483349,
        "profit_factor": 4.519594497090299,
        "pnl_dollars": 1197017.583821158,
        "max_drawdown": -5545.832033190643,
        "avg_pnl": 569.4660246532626,
        "avg_hold_minutes": 159.95718363463368,
        "long_rate": 0.5499524262607041,
        "avg_delta_abs": 0.5806020456707898
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.615931721194879,
          "profit_factor": 3.9290388042392657,
          "pnl_dollars": 293507.6849040446,
          "max_drawdown": -4673.096297794196,
          "avg_pnl": 417.50737539693404,
          "avg_hold_minutes": 157.07681365576101,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.5431961593172119
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7097701149425287,
          "profit_factor": 5.204010972007349,
          "pnl_dollars": 605759.1697983294,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 870.3436347677145,
          "avg_hold_minutes": 162.9022988505747,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.646619683908046
        },
        "SPY": {
          "trades": 703,
          "win_rate": 0.65149359886202,
          "profit_factor": 4.107912799975117,
          "pnl_dollars": 297750.72911878396,
          "max_drawdown": -3811.259283054911,
          "avg_pnl": 423.54300016896724,
          "avg_hold_minutes": 159.9217638691323,
          "long_rate": 0.5448079658605974,
          "avg_delta_abs": 0.552647652916074
        }
      }
    },
    "option_value_best_select_hard": {
      "overall": {
        "trades": 2102,
        "win_rate": 0.5156993339676499,
        "profit_factor": 2.8754504063683357,
        "pnl_dollars": 1086233.0201366127,
        "max_drawdown": -9197.668227685848,
        "avg_pnl": 516.7616651458671,
        "avg_hold_minutes": 143.37059942911512,
        "long_rate": 0.5499524262607041,
        "avg_delta_abs": 0.4005011893434824
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.40825035561877665,
          "profit_factor": 2.103658441092321,
          "pnl_dollars": 242386.6054048107,
          "max_drawdown": -10319.551838272571,
          "avg_pnl": 344.7889123823765,
          "avg_hold_minutes": 131.4580369843528,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.27263499288762444
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.7112068965517241,
          "profit_factor": 5.018861493876295,
          "pnl_dollars": 622021.1219676685,
          "max_drawdown": -5653.03962098388,
          "avg_pnl": 893.7085085742364,
          "avg_hold_minutes": 163.36925287356323,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.6465159482758621
        },
        "SPY": {
          "trades": 703,
          "win_rate": 0.4295874822190612,
          "profit_factor": 2.083191292992567,
          "pnl_dollars": 221825.29276413348,
          "max_drawdown": -7917.553024284993,
          "avg_pnl": 315.54095699023253,
          "avg_hold_minutes": 135.48364153627313,
          "long_rate": 0.5448079658605974,
          "avg_delta_abs": 0.2848022759601707
        }
      }
    },
    "option_value_best_select_learned_exit_5m": {
      "overall": {
        "trades": 2100,
        "win_rate": 0.5214285714285715,
        "profit_factor": 2.809993042424788,
        "pnl_dollars": 1019088.1899978031,
        "max_drawdown": -8447.37562482385,
        "avg_pnl": 485.28009047514433,
        "avg_hold_minutes": 137.73333333333332,
        "long_rate": 0.5495238095238095,
        "avg_delta_abs": 0.40045780952380955
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.4096728307254623,
          "profit_factor": 2.142793527492571,
          "pnl_dollars": 250245.39481884043,
          "max_drawdown": -10751.689452236169,
          "avg_pnl": 355.9678446925184,
          "avg_hold_minutes": 132.8805120910384,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.27263499288762444
        },
        "SPX": {
          "trades": 696,
          "win_rate": 0.728448275862069,
          "profit_factor": 4.715266310120626,
          "pnl_dollars": 526932.9480359358,
          "max_drawdown": -5545.832033190527,
          "avg_pnl": 757.0875690171491,
          "avg_hold_minutes": 143.29741379310346,
          "long_rate": 0.5517241379310345,
          "avg_delta_abs": 0.6465159482758621
        },
        "SPY": {
          "trades": 701,
          "win_rate": 0.42796005706134094,
          "profit_factor": 2.19622162302611,
          "pnl_dollars": 241909.84714302688,
          "max_drawdown": -8266.715902311436,
          "avg_pnl": 345.0925066234335,
          "avg_hold_minutes": 137.0756062767475,
          "long_rate": 0.543509272467903,
          "avg_delta_abs": 0.28434222539229675
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 2102,
        "win_rate": 0.7450047573739296,
        "profit_factor": 14.030179306231027,
        "pnl_dollars": 2090505.2574139247,
        "max_drawdown": -2092.563934390899,
        "avg_pnl": 994.5315211293647,
        "avg_hold_minutes": 155.11893434823978,
        "long_rate": 0.5499524262607041,
        "avg_delta_abs": 0.5305908658420553
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.7254623044096729,
          "profit_factor": 13.023224793496082,
          "pnl_dollars": 622758.7481106198,
          "max_drawdown": -1703.3687367737293,
          "avg_pnl": 885.8588166580652,
          "avg_hold_minutes": 156.09530583214794,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.5147082503556187
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
          "trades": 703,
          "win_rate": 0.748221906116643,
          "profit_factor": 11.81311247756333,
          "pnl_dollars": 596527.398356464,
          "max_drawdown": -1978.831441511029,
          "avg_pnl": 848.5453746180142,
          "avg_hold_minutes": 156.57894736842104,
          "long_rate": 0.5448079658605974,
          "avg_delta_abs": 0.5050234708392604
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 2102,
        "win_rate": 0.9590865842055185,
        "profit_factor": 644.9619049336653,
        "pnl_dollars": 4266644.730126997,
        "max_drawdown": -342.42661216761917,
        "avg_pnl": 2029.8024405932433,
        "avg_hold_minutes": 114.59086584205518,
        "long_rate": 0.5499524262607041,
        "avg_delta_abs": 0.38681265461465275
      },
      "per_ticker": {
        "QQQ": {
          "trades": 703,
          "win_rate": 0.9630156472261735,
          "profit_factor": 630.7842642922218,
          "pnl_dollars": 1390820.677995669,
          "max_drawdown": -342.42661216761917,
          "avg_pnl": 1978.4077923124737,
          "avg_hold_minutes": 110.29871977240398,
          "long_rate": 0.5533428165007113,
          "avg_delta_abs": 0.32526301564722615
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
          "trades": 703,
          "win_rate": 0.9502133712660028,
          "profit_factor": 493.0782456267715,
          "pnl_dollars": 1249480.5987412976,
          "max_drawdown": -215.74634395036264,
          "avg_pnl": 1777.355047996156,
          "avg_hold_minutes": 112.87339971550497,
          "long_rate": 0.5448079658605974,
          "avg_delta_abs": 0.32940455192034146
        }
      }
    }
  }
}
```
