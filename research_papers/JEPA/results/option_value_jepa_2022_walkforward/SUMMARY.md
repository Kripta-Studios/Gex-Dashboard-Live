# OptionValueJEPA Walk-Forward Since 2022

Candidate labels: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\results\jepa_option_policy_2022\candidate_labels.parquet`
Train start: `20220801`
Min train months: `12`
Epochs per fold: `8`
Exit margin: `-0.3`

## Overall Walk-Forward Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 2099 | 58.1% | 3.005 | +794,618 | -6,442 | +379 | 135.5 | 0.703 |
| option_value_hold180_select_hard | 2099 | 47.3% | 2.458 | +707,925 | -8,021 | +337 | 119.3 | 0.576 |
| option_value_rule_select_hard | 2099 | 50.1% | 2.625 | +716,498 | -6,963 | +341 | 123.3 | 0.613 |
| option_value_best_select_hard | 2099 | 35.1% | 2.004 | +633,844 | -17,985 | +302 | 96.2 | 0.396 |
| option_value_best_select_learned_exit_5m | 2099 | 35.9% | 1.872 | +543,044 | -20,182 | +259 | 87.6 | 0.396 |
| oracle_best_delta_hard | 2099 | 58.2% | 7.311 | +1,542,132 | -2,334 | +735 | 120.2 | 0.523 |
| oracle_best_delta_oracle_exit | 2099 | 95.9% | 643.263 | +4,255,387 | -342 | +2,027 | 114.5 | 0.387 |

## Fold Metrics

| Month | Policy | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202308 | fixed_delta_0.70_hard | 68 | 57.4% | 2.925 | +18,020 | -1,367 |
| 202308 | option_value_hold180_select_hard | 68 | 48.5% | 1.716 | +9,804 | -1,983 |
| 202308 | option_value_rule_select_hard | 68 | 50.0% | 1.916 | +11,735 | -2,185 |
| 202308 | option_value_best_select_hard | 68 | 33.8% | 1.402 | +7,722 | -5,352 |
| 202308 | option_value_best_select_learned_exit_5m | 68 | 33.8% | 1.362 | +6,957 | -5,352 |
| 202308 | oracle_best_delta_hard | 68 | 57.4% | 6.441 | +38,619 | -722 |
| 202308 | oracle_best_delta_oracle_exit | 68 | 98.5% | 11085.873 | +101,623 | -9 |
| 202309 | fixed_delta_0.70_hard | 60 | 46.7% | 1.399 | +5,233 | -4,458 |
| 202309 | option_value_hold180_select_hard | 60 | 35.0% | 1.221 | +3,517 | -4,355 |
| 202309 | option_value_rule_select_hard | 60 | 38.3% | 1.190 | +2,912 | -4,355 |
| 202309 | option_value_best_select_hard | 60 | 28.3% | 1.196 | +3,746 | -4,448 |
| 202309 | option_value_best_select_learned_exit_5m | 60 | 28.3% | 1.111 | +2,123 | -5,653 |
| 202309 | oracle_best_delta_hard | 60 | 46.7% | 3.098 | +19,916 | -1,800 |
| 202309 | oracle_best_delta_oracle_exit | 60 | 88.3% | 101.022 | +76,210 | -216 |
| 202310 | fixed_delta_0.70_hard | 66 | 48.5% | 2.669 | +26,211 | -6,442 |
| 202310 | option_value_hold180_select_hard | 66 | 40.9% | 2.387 | +24,445 | -6,442 |
| 202310 | option_value_rule_select_hard | 66 | 47.0% | 2.791 | +28,046 | -5,919 |
| 202310 | option_value_best_select_hard | 66 | 33.3% | 2.630 | +35,089 | -6,442 |
| 202310 | option_value_best_select_learned_exit_5m | 66 | 34.8% | 2.605 | +33,787 | -6,442 |
| 202310 | oracle_best_delta_hard | 66 | 48.5% | 7.211 | +59,095 | -2,334 |
| 202310 | oracle_best_delta_oracle_exit | 66 | 90.9% | 890.445 | +177,524 | -134 |
| 202311 | fixed_delta_0.70_hard | 63 | 58.7% | 2.994 | +17,728 | -1,547 |
| 202311 | option_value_hold180_select_hard | 63 | 52.4% | 2.811 | +17,756 | -1,983 |
| 202311 | option_value_rule_select_hard | 63 | 52.4% | 2.936 | +17,521 | -1,983 |
| 202311 | option_value_best_select_hard | 63 | 39.7% | 1.853 | +13,723 | -2,846 |
| 202311 | option_value_best_select_learned_exit_5m | 63 | 41.3% | 1.778 | +11,901 | -2,846 |
| 202311 | oracle_best_delta_hard | 63 | 58.7% | 5.496 | +33,680 | -1,547 |
| 202311 | oracle_best_delta_oracle_exit | 63 | 95.2% | 385.207 | +115,398 | -123 |
| 202312 | fixed_delta_0.70_hard | 59 | 57.6% | 2.215 | +11,529 | -1,390 |
| 202312 | option_value_hold180_select_hard | 59 | 54.2% | 2.147 | +11,688 | -2,077 |
| 202312 | option_value_rule_select_hard | 59 | 55.9% | 2.273 | +12,115 | -1,299 |
| 202312 | option_value_best_select_hard | 59 | 40.7% | 1.673 | +9,139 | -2,441 |
| 202312 | option_value_best_select_learned_exit_5m | 59 | 40.7% | 2.095 | +14,875 | -2,441 |
| 202312 | oracle_best_delta_hard | 59 | 57.6% | 5.730 | +33,747 | -936 |
| 202312 | oracle_best_delta_oracle_exit | 59 | 100.0% | nan | +83,091 | +0 |
| 202401 | fixed_delta_0.70_hard | 63 | 69.8% | 5.238 | +31,450 | -1,067 |
| 202401 | option_value_hold180_select_hard | 63 | 58.7% | 4.130 | +30,387 | -1,554 |
| 202401 | option_value_rule_select_hard | 63 | 60.3% | 3.848 | +25,863 | -1,436 |
| 202401 | option_value_best_select_hard | 63 | 49.2% | 4.034 | +39,608 | -3,233 |
| 202401 | option_value_best_select_learned_exit_5m | 63 | 47.6% | 3.610 | +34,979 | -3,233 |
| 202401 | oracle_best_delta_hard | 63 | 69.8% | 13.113 | +67,188 | -826 |
| 202401 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +153,426 | +0 |
| 202402 | fixed_delta_0.70_hard | 60 | 66.7% | 4.756 | +28,396 | -1,546 |
| 202402 | option_value_hold180_select_hard | 60 | 63.3% | 5.274 | +34,872 | -1,437 |
| 202402 | option_value_rule_select_hard | 60 | 65.0% | 4.521 | +28,249 | -1,510 |
| 202402 | option_value_best_select_hard | 60 | 48.3% | 3.739 | +33,605 | -2,386 |
| 202402 | option_value_best_select_learned_exit_5m | 60 | 50.0% | 3.723 | +33,401 | -2,386 |
| 202402 | oracle_best_delta_hard | 60 | 66.7% | 10.892 | +56,951 | -1,245 |
| 202402 | oracle_best_delta_oracle_exit | 60 | 96.7% | 409.816 | +116,332 | -144 |
| 202403 | fixed_delta_0.70_hard | 60 | 66.7% | 2.641 | +12,807 | -1,221 |
| 202403 | option_value_hold180_select_hard | 60 | 60.0% | 2.454 | +13,344 | -1,312 |
| 202403 | option_value_rule_select_hard | 60 | 60.0% | 2.524 | +13,116 | -1,224 |
| 202403 | option_value_best_select_hard | 60 | 28.3% | 1.327 | +5,513 | -2,965 |
| 202403 | option_value_best_select_learned_exit_5m | 60 | 30.0% | 1.398 | +6,577 | -2,965 |
| 202403 | oracle_best_delta_hard | 60 | 66.7% | 6.511 | +31,621 | -1,026 |
| 202403 | oracle_best_delta_oracle_exit | 60 | 93.3% | 386.165 | +92,858 | -110 |
| 202404 | fixed_delta_0.70_hard | 65 | 63.1% | 4.104 | +29,607 | -1,984 |
| 202404 | option_value_hold180_select_hard | 65 | 46.2% | 3.107 | +28,791 | -2,182 |
| 202404 | option_value_rule_select_hard | 65 | 47.7% | 3.404 | +28,541 | -1,725 |
| 202404 | option_value_best_select_hard | 65 | 33.8% | 2.373 | +25,997 | -3,214 |
| 202404 | option_value_best_select_learned_exit_5m | 65 | 36.9% | 2.794 | +31,909 | -3,214 |
| 202404 | oracle_best_delta_hard | 65 | 63.1% | 8.409 | +49,832 | -1,332 |
| 202404 | oracle_best_delta_oracle_exit | 65 | 96.9% | 1186.668 | +234,674 | -116 |
| 202405 | fixed_delta_0.70_hard | 66 | 53.0% | 2.141 | +12,014 | -1,943 |
| 202405 | option_value_hold180_select_hard | 66 | 33.3% | 1.310 | +4,860 | -2,492 |
| 202405 | option_value_rule_select_hard | 66 | 39.4% | 1.544 | +7,332 | -2,386 |
| 202405 | option_value_best_select_hard | 66 | 25.8% | 0.925 | -1,434 | -7,201 |
| 202405 | option_value_best_select_learned_exit_5m | 66 | 27.3% | 0.911 | -1,709 | -6,711 |
| 202405 | oracle_best_delta_hard | 66 | 53.0% | 3.604 | +21,375 | -1,314 |
| 202405 | oracle_best_delta_oracle_exit | 66 | 92.4% | 401.349 | +98,201 | -179 |
| 202406 | fixed_delta_0.70_hard | 57 | 56.1% | 2.382 | +14,012 | -1,706 |
| 202406 | option_value_hold180_select_hard | 57 | 42.1% | 2.672 | +19,543 | -2,492 |
| 202406 | option_value_rule_select_hard | 57 | 47.4% | 2.184 | +13,101 | -2,200 |
| 202406 | option_value_best_select_hard | 57 | 38.6% | 2.121 | +16,263 | -3,406 |
| 202406 | option_value_best_select_learned_exit_5m | 57 | 38.6% | 1.940 | +13,644 | -3,406 |
| 202406 | oracle_best_delta_hard | 57 | 56.1% | 6.298 | +37,291 | -1,596 |
| 202406 | oracle_best_delta_oracle_exit | 57 | 100.0% | nan | +183,763 | +0 |
| 202407 | fixed_delta_0.70_hard | 66 | 62.1% | 2.181 | +15,161 | -4,155 |
| 202407 | option_value_hold180_select_hard | 66 | 50.0% | 1.901 | +13,795 | -4,155 |
| 202407 | option_value_rule_select_hard | 66 | 54.5% | 2.184 | +15,859 | -4,353 |
| 202407 | option_value_best_select_hard | 66 | 33.3% | 1.497 | +10,447 | -4,158 |
| 202407 | option_value_best_select_learned_exit_5m | 66 | 31.8% | 1.345 | +7,412 | -4,158 |
| 202407 | oracle_best_delta_hard | 66 | 62.1% | 6.880 | +41,396 | -689 |
| 202407 | oracle_best_delta_oracle_exit | 66 | 95.5% | 315.692 | +115,699 | -156 |
| 202408 | fixed_delta_0.70_hard | 66 | 53.0% | 2.439 | +23,573 | -4,861 |
| 202408 | option_value_hold180_select_hard | 66 | 42.4% | 1.913 | +17,167 | -3,501 |
| 202408 | option_value_rule_select_hard | 66 | 42.4% | 1.850 | +14,907 | -5,627 |
| 202408 | option_value_best_select_hard | 66 | 30.3% | 1.748 | +18,021 | -5,022 |
| 202408 | option_value_best_select_learned_exit_5m | 66 | 31.8% | 1.462 | +10,775 | -5,022 |
| 202408 | oracle_best_delta_hard | 66 | 53.0% | 6.245 | +44,727 | -1,643 |
| 202408 | oracle_best_delta_oracle_exit | 66 | 92.4% | 342.088 | +118,528 | -138 |
| 202409 | fixed_delta_0.70_hard | 60 | 70.0% | 5.504 | +34,134 | -1,103 |
| 202409 | option_value_hold180_select_hard | 60 | 56.7% | 4.253 | +34,026 | -1,103 |
| 202409 | option_value_rule_select_hard | 60 | 58.3% | 4.949 | +31,914 | -1,065 |
| 202409 | option_value_best_select_hard | 60 | 40.0% | 2.644 | +27,639 | -3,395 |
| 202409 | option_value_best_select_learned_exit_5m | 60 | 41.7% | 2.602 | +26,301 | -3,395 |
| 202409 | oracle_best_delta_hard | 60 | 70.0% | 14.992 | +61,351 | -633 |
| 202409 | oracle_best_delta_oracle_exit | 60 | 98.3% | 20599.806 | +141,809 | -7 |
| 202410 | fixed_delta_0.70_hard | 69 | 59.4% | 3.020 | +24,171 | -1,881 |
| 202410 | option_value_hold180_select_hard | 69 | 43.5% | 1.958 | +16,354 | -2,694 |
| 202410 | option_value_rule_select_hard | 69 | 50.7% | 2.409 | +21,308 | -2,043 |
| 202410 | option_value_best_select_hard | 69 | 31.9% | 1.531 | +10,038 | -4,444 |
| 202410 | option_value_best_select_learned_exit_5m | 69 | 31.9% | 1.559 | +10,569 | -4,682 |
| 202410 | oracle_best_delta_hard | 69 | 59.4% | 6.866 | +43,573 | -1,088 |
| 202410 | oracle_best_delta_oracle_exit | 69 | 97.1% | 2965.577 | +115,797 | -24 |
| 202411 | fixed_delta_0.70_hard | 60 | 58.3% | 3.680 | +22,507 | -1,598 |
| 202411 | option_value_hold180_select_hard | 60 | 48.3% | 2.981 | +19,932 | -1,461 |
| 202411 | option_value_rule_select_hard | 60 | 50.0% | 3.145 | +20,423 | -1,441 |
| 202411 | option_value_best_select_hard | 60 | 45.0% | 3.980 | +38,637 | -1,982 |
| 202411 | option_value_best_select_learned_exit_5m | 60 | 48.3% | 4.043 | +37,943 | -1,982 |
| 202411 | oracle_best_delta_hard | 60 | 60.0% | 12.063 | +67,015 | -926 |
| 202411 | oracle_best_delta_oracle_exit | 60 | 98.3% | 580.346 | +108,296 | -187 |
| 202412 | fixed_delta_0.70_hard | 62 | 45.2% | 1.431 | +6,080 | -3,571 |
| 202412 | option_value_hold180_select_hard | 62 | 37.1% | 1.391 | +6,221 | -3,591 |
| 202412 | option_value_rule_select_hard | 62 | 41.9% | 1.608 | +8,191 | -2,590 |
| 202412 | option_value_best_select_hard | 62 | 25.8% | 1.084 | +1,706 | -3,901 |
| 202412 | option_value_best_select_learned_exit_5m | 62 | 27.4% | 0.937 | -1,273 | -4,678 |
| 202412 | oracle_best_delta_hard | 62 | 45.2% | 3.523 | +25,090 | -1,782 |
| 202412 | oracle_best_delta_oracle_exit | 62 | 98.4% | 1660.548 | +91,034 | -55 |
| 202501 | fixed_delta_0.70_hard | 60 | 55.0% | 3.307 | +30,310 | -5,479 |
| 202501 | option_value_hold180_select_hard | 60 | 45.0% | 2.397 | +22,757 | -5,479 |
| 202501 | option_value_rule_select_hard | 60 | 46.7% | 2.273 | +20,256 | -6,963 |
| 202501 | option_value_best_select_hard | 60 | 36.7% | 1.999 | +19,918 | -5,622 |
| 202501 | option_value_best_select_learned_exit_5m | 60 | 36.7% | 1.756 | +15,067 | -5,707 |
| 202501 | oracle_best_delta_hard | 60 | 55.0% | 7.304 | +47,632 | -1,578 |
| 202501 | oracle_best_delta_oracle_exit | 60 | 96.7% | 382.901 | +152,963 | -208 |
| 202502 | fixed_delta_0.70_hard | 57 | 61.4% | 3.559 | +27,997 | -2,250 |
| 202502 | option_value_hold180_select_hard | 57 | 42.1% | 2.496 | +22,751 | -2,586 |
| 202502 | option_value_rule_select_hard | 57 | 45.6% | 2.982 | +26,887 | -2,313 |
| 202502 | option_value_best_select_hard | 57 | 33.3% | 2.177 | +21,199 | -3,115 |
| 202502 | option_value_best_select_learned_exit_5m | 57 | 35.1% | 2.443 | +25,924 | -3,115 |
| 202502 | oracle_best_delta_hard | 57 | 61.4% | 8.649 | +47,841 | -938 |
| 202502 | oracle_best_delta_oracle_exit | 57 | 96.5% | 1151.387 | +151,151 | -74 |
| 202503 | fixed_delta_0.70_hard | 63 | 74.6% | 6.003 | +58,572 | -2,444 |
| 202503 | option_value_hold180_select_hard | 63 | 65.1% | 5.415 | +61,516 | -2,444 |
| 202503 | option_value_rule_select_hard | 63 | 69.8% | 6.680 | +64,877 | -2,444 |
| 202503 | option_value_best_select_hard | 63 | 47.6% | 3.922 | +55,553 | -3,450 |
| 202503 | option_value_best_select_learned_exit_5m | 63 | 47.6% | 3.187 | +41,578 | -3,450 |
| 202503 | oracle_best_delta_hard | 63 | 74.6% | 19.893 | +88,152 | -634 |
| 202503 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +180,300 | +0 |
| 202504 | fixed_delta_0.70_hard | 60 | 65.0% | 5.639 | +83,761 | -4,022 |
| 202504 | option_value_hold180_select_hard | 60 | 46.7% | 4.599 | +76,362 | -3,717 |
| 202504 | option_value_rule_select_hard | 60 | 48.3% | 4.584 | +73,299 | -3,717 |
| 202504 | option_value_best_select_hard | 60 | 31.7% | 3.415 | +64,924 | -4,108 |
| 202504 | option_value_best_select_learned_exit_5m | 60 | 33.3% | 2.100 | +27,909 | -5,092 |
| 202504 | oracle_best_delta_hard | 60 | 66.7% | 21.019 | +113,283 | -610 |
| 202504 | oracle_best_delta_oracle_exit | 60 | 93.3% | 588.020 | +249,111 | -168 |
| 202505 | fixed_delta_0.70_hard | 63 | 65.1% | 3.633 | +28,072 | -3,179 |
| 202505 | option_value_hold180_select_hard | 63 | 50.8% | 2.380 | +18,054 | -2,922 |
| 202505 | option_value_rule_select_hard | 63 | 57.1% | 2.869 | +20,122 | -2,667 |
| 202505 | option_value_best_select_hard | 63 | 42.9% | 1.984 | +16,740 | -3,240 |
| 202505 | option_value_best_select_learned_exit_5m | 63 | 44.4% | 2.351 | +20,712 | -3,099 |
| 202505 | oracle_best_delta_hard | 63 | 65.1% | 12.583 | +63,227 | -996 |
| 202505 | oracle_best_delta_oracle_exit | 63 | 98.4% | 2535.697 | +149,233 | -59 |
| 202506 | fixed_delta_0.70_hard | 60 | 58.3% | 2.699 | +18,304 | -1,232 |
| 202506 | option_value_hold180_select_hard | 60 | 45.0% | 1.866 | +12,695 | -3,328 |
| 202506 | option_value_rule_select_hard | 60 | 50.0% | 2.459 | +16,742 | -2,323 |
| 202506 | option_value_best_select_hard | 60 | 30.0% | 1.354 | +6,509 | -3,350 |
| 202506 | option_value_best_select_learned_exit_5m | 60 | 33.3% | 1.518 | +9,206 | -3,350 |
| 202506 | oracle_best_delta_hard | 60 | 58.3% | 6.031 | +34,577 | -646 |
| 202506 | oracle_best_delta_oracle_exit | 60 | 95.0% | 1927.640 | +98,648 | -24 |
| 202507 | fixed_delta_0.70_hard | 66 | 65.2% | 3.459 | +21,466 | -968 |
| 202507 | option_value_hold180_select_hard | 66 | 63.6% | 3.494 | +22,324 | -1,027 |
| 202507 | option_value_rule_select_hard | 66 | 60.6% | 3.257 | +19,587 | -1,020 |
| 202507 | option_value_best_select_hard | 66 | 40.9% | 1.792 | +12,096 | -2,411 |
| 202507 | option_value_best_select_learned_exit_5m | 66 | 40.9% | 1.731 | +11,171 | -2,411 |
| 202507 | oracle_best_delta_hard | 66 | 65.2% | 5.933 | +31,797 | -790 |
| 202507 | oracle_best_delta_oracle_exit | 66 | 98.5% | 707.565 | +83,050 | -118 |
| 202508 | fixed_delta_0.70_hard | 63 | 55.6% | 1.967 | +11,058 | -1,838 |
| 202508 | option_value_hold180_select_hard | 63 | 38.1% | 1.151 | +2,353 | -3,098 |
| 202508 | option_value_rule_select_hard | 63 | 44.4% | 1.311 | +4,305 | -2,819 |
| 202508 | option_value_best_select_hard | 63 | 30.2% | 1.116 | +2,139 | -5,674 |
| 202508 | option_value_best_select_learned_exit_5m | 63 | 30.2% | 1.246 | +4,561 | -5,674 |
| 202508 | oracle_best_delta_hard | 63 | 55.6% | 3.565 | +20,774 | -1,656 |
| 202508 | oracle_best_delta_oracle_exit | 63 | 100.0% | nan | +60,602 | +0 |
| 202509 | fixed_delta_0.70_hard | 62 | 53.2% | 2.726 | +21,292 | -3,405 |
| 202509 | option_value_hold180_select_hard | 62 | 45.2% | 2.310 | +19,024 | -3,512 |
| 202509 | option_value_rule_select_hard | 62 | 51.6% | 2.812 | +22,451 | -3,491 |
| 202509 | option_value_best_select_hard | 62 | 38.7% | 1.974 | +18,205 | -3,503 |
| 202509 | option_value_best_select_learned_exit_5m | 62 | 38.7% | 2.024 | +19,141 | -3,503 |
| 202509 | oracle_best_delta_hard | 62 | 53.2% | 6.227 | +41,684 | -1,367 |
| 202509 | oracle_best_delta_oracle_exit | 62 | 96.8% | 559.154 | +104,486 | -99 |
| 202510 | fixed_delta_0.70_hard | 67 | 80.6% | 10.488 | +53,689 | -1,022 |
| 202510 | option_value_hold180_select_hard | 67 | 68.7% | 6.622 | +50,857 | -1,305 |
| 202510 | option_value_rule_select_hard | 67 | 73.1% | 7.867 | +52,698 | -1,248 |
| 202510 | option_value_best_select_hard | 67 | 58.2% | 5.665 | +55,403 | -2,783 |
| 202510 | option_value_best_select_learned_exit_5m | 67 | 59.7% | 5.426 | +50,565 | -2,330 |
| 202510 | oracle_best_delta_hard | 67 | 80.6% | 28.440 | +93,324 | -369 |
| 202510 | oracle_best_delta_oracle_exit | 67 | 97.0% | 1349.134 | +197,040 | -78 |
| 202511 | fixed_delta_0.70_hard | 57 | 57.9% | 4.063 | +37,165 | -2,938 |
| 202511 | option_value_hold180_select_hard | 57 | 45.6% | 3.375 | +37,282 | -2,938 |
| 202511 | option_value_rule_select_hard | 57 | 47.4% | 3.638 | +40,063 | -2,938 |
| 202511 | option_value_best_select_hard | 57 | 38.6% | 3.073 | +37,334 | -2,994 |
| 202511 | option_value_best_select_learned_exit_5m | 57 | 36.8% | 2.292 | +23,678 | -2,938 |
| 202511 | oracle_best_delta_hard | 57 | 57.9% | 10.451 | +64,061 | -793 |
| 202511 | oracle_best_delta_oracle_exit | 57 | 100.0% | nan | +148,869 | +0 |
| 202512 | fixed_delta_0.70_hard | 65 | 56.9% | 2.059 | +12,736 | -2,273 |
| 202512 | option_value_hold180_select_hard | 65 | 44.6% | 1.838 | +12,034 | -2,273 |
| 202512 | option_value_rule_select_hard | 65 | 44.6% | 1.724 | +9,651 | -3,264 |
| 202512 | option_value_best_select_hard | 65 | 26.2% | 0.963 | -763 | -6,732 |
| 202512 | option_value_best_select_learned_exit_5m | 65 | 26.2% | 0.945 | -1,145 | -6,555 |
| 202512 | oracle_best_delta_hard | 65 | 56.9% | 3.917 | +22,296 | -1,083 |
| 202512 | oracle_best_delta_oracle_exit | 65 | 92.3% | 221.440 | +67,838 | -112 |
| 202601 | fixed_delta_0.70_hard | 60 | 43.3% | 1.198 | +3,284 | -4,658 |
| 202601 | option_value_hold180_select_hard | 60 | 25.0% | 0.752 | -5,179 | -8,021 |
| 202601 | option_value_rule_select_hard | 60 | 33.3% | 0.934 | -1,248 | -6,039 |
| 202601 | option_value_best_select_hard | 60 | 11.7% | 0.410 | -15,048 | -15,950 |
| 202601 | option_value_best_select_learned_exit_5m | 60 | 11.7% | 0.460 | -13,781 | -14,682 |
| 202601 | oracle_best_delta_hard | 60 | 43.3% | 2.209 | +12,192 | -1,665 |
| 202601 | oracle_best_delta_oracle_exit | 60 | 95.0% | 1934.127 | +99,862 | -25 |
| 202602 | fixed_delta_0.70_hard | 56 | 51.8% | 1.386 | +6,356 | -4,811 |
| 202602 | option_value_hold180_select_hard | 56 | 44.6% | 1.237 | +4,340 | -4,811 |
| 202602 | option_value_rule_select_hard | 56 | 44.6% | 1.127 | +2,312 | -6,005 |
| 202602 | option_value_best_select_hard | 56 | 30.4% | 1.167 | +3,838 | -5,256 |
| 202602 | option_value_best_select_learned_exit_5m | 56 | 30.4% | 0.975 | -582 | -6,766 |
| 202602 | oracle_best_delta_hard | 56 | 51.8% | 4.839 | +29,520 | -1,048 |
| 202602 | oracle_best_delta_oracle_exit | 56 | 96.4% | 454.100 | +72,018 | -102 |
| 202603 | fixed_delta_0.70_hard | 66 | 47.0% | 2.559 | +26,434 | -5,706 |
| 202603 | option_value_hold180_select_hard | 66 | 39.4% | 2.095 | +23,323 | -5,706 |
| 202603 | option_value_rule_select_hard | 66 | 42.4% | 2.358 | +26,531 | -5,424 |
| 202603 | option_value_best_select_hard | 66 | 25.8% | 1.734 | +18,804 | -5,706 |
| 202603 | option_value_best_select_learned_exit_5m | 66 | 27.3% | 1.371 | +9,336 | -5,733 |
| 202603 | oracle_best_delta_hard | 66 | 47.0% | 5.799 | +44,813 | -1,827 |
| 202603 | oracle_best_delta_oracle_exit | 66 | 95.5% | 1023.631 | +149,081 | -88 |
| 202604 | fixed_delta_0.70_hard | 52 | 46.2% | 1.866 | +11,261 | -2,669 |
| 202604 | option_value_hold180_select_hard | 52 | 44.2% | 1.727 | +9,970 | -2,669 |
| 202604 | option_value_rule_select_hard | 52 | 40.4% | 1.527 | +7,148 | -2,669 |
| 202604 | option_value_best_select_hard | 52 | 34.6% | 1.860 | +14,293 | -4,559 |
| 202604 | option_value_best_select_learned_exit_5m | 52 | 34.6% | 1.794 | +13,187 | -4,559 |
| 202604 | oracle_best_delta_hard | 52 | 46.2% | 4.545 | +30,268 | -1,762 |
| 202604 | oracle_best_delta_oracle_exit | 52 | 80.8% | 87.592 | +94,580 | -342 |
| 202605 | fixed_delta_0.70_hard | 52 | 40.4% | 1.692 | +10,226 | -2,693 |
| 202605 | option_value_hold180_select_hard | 52 | 38.5% | 1.692 | +10,962 | -2,456 |
| 202605 | option_value_rule_select_hard | 52 | 36.5% | 1.675 | +9,681 | -2,845 |
| 202605 | option_value_best_select_hard | 52 | 26.9% | 1.372 | +7,241 | -5,528 |
| 202605 | option_value_best_select_learned_exit_5m | 52 | 28.8% | 1.332 | +6,346 | -5,528 |
| 202605 | oracle_best_delta_hard | 52 | 40.4% | 3.768 | +24,222 | -1,187 |
| 202605 | oracle_best_delta_oracle_exit | 52 | 94.2% | 663.096 | +72,293 | -104 |

## Config

```json
{
  "args": {
    "data": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\training_data\\training_data_spx_qqq_spy_jepa_xinput_v3.parquet",
    "candidate_labels": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\research_papers\\JEPA\\results\\jepa_option_policy_2022\\candidate_labels.parquet",
    "output_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\research_papers\\JEPA\\results\\option_value_jepa_2022_walkforward",
    "train_start_date": "20220801",
    "min_train_months": 12,
    "start_month": "",
    "end_month": "",
    "max_folds": 0,
    "risk_capital": 1000.0,
    "max_hold_minutes": 180,
    "hard_stop_pct": -0.35,
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
    "device": "",
    "log_every_epochs": 4
  },
  "candidate_rows": 19551,
  "state_rows": 703836,
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
        "trades": 2099,
        "win_rate": 0.5812291567413054,
        "profit_factor": 3.0054197997374863,
        "pnl_dollars": 794617.9669994216,
        "max_drawdown": -6442.06354986666,
        "avg_pnl": 378.5697794184953,
        "avg_hold_minutes": 135.49070986183898,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.7027401619818961
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.5754985754985755,
          "profit_factor": 2.9073107498916144,
          "pnl_dollars": 173864.11257482533,
          "max_drawdown": -3011.280920929974,
          "avg_pnl": 247.6696760325147,
          "avg_hold_minutes": 136.01139601139602,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.7036631054131054
        },
        "SPX": {
          "trades": 695,
          "win_rate": 0.5798561151079137,
          "profit_factor": 3.101429514775382,
          "pnl_dollars": 449860.96205051895,
          "max_drawdown": -6442.0635498666525,
          "avg_pnl": 647.2819597849193,
          "avg_hold_minutes": 132.9208633093525,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.7008448920863309
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.5883190883190883,
          "profit_factor": 2.877845518641114,
          "pnl_dollars": 170892.89237407743,
          "max_drawdown": -2853.039188570445,
          "avg_pnl": 243.43716862404193,
          "avg_hold_minutes": 137.514245014245,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.7036935897435896
        }
      }
    },
    "option_value_hold180_select_hard": {
      "overall": {
        "trades": 2099,
        "win_rate": 0.4730824202000953,
        "profit_factor": 2.4578207440277966,
        "pnl_dollars": 707925.4922231509,
        "max_drawdown": -8021.474205724429,
        "avg_pnl": 337.2679810496193,
        "avg_hold_minutes": 119.32825154835636,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.576313768461172
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.4444444444444444,
          "profit_factor": 2.1119728948925878,
          "pnl_dollars": 149967.19838707865,
          "max_drawdown": -4560.457688261755,
          "avg_pnl": 213.62848773088126,
          "avg_hold_minutes": 115.13532763532764,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.5340267806267807
        },
        "SPX": {
          "trades": 695,
          "win_rate": 0.5266187050359712,
          "profit_factor": 2.8552038356663907,
          "pnl_dollars": 402694.14823298855,
          "max_drawdown": -6442.063549866651,
          "avg_pnl": 579.4160406230051,
          "avg_hold_minutes": 125.61151079136691,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.6548261870503597
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.44871794871794873,
          "profit_factor": 2.1614830987285556,
          "pnl_dollars": 155264.14560308369,
          "max_drawdown": -5354.657904716732,
          "avg_pnl": 221.1739965855893,
          "avg_hold_minutes": 117.3005698005698,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.5408712250712251
        }
      }
    },
    "option_value_rule_select_hard": {
      "overall": {
        "trades": 2099,
        "win_rate": 0.5011910433539781,
        "profit_factor": 2.6249632681846196,
        "pnl_dollars": 716497.5461507955,
        "max_drawdown": -6962.608695884177,
        "avg_pnl": 341.35185619380445,
        "avg_hold_minutes": 123.29680800381134,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.6129856598380181
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.4985754985754986,
          "profit_factor": 2.4522952479154814,
          "pnl_dollars": 170360.83859869608,
          "max_drawdown": -3584.22037481195,
          "avg_pnl": 242.67925726309983,
          "avg_hold_minutes": 124.06695156695157,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.61027150997151
        },
        "SPX": {
          "trades": 695,
          "win_rate": 0.5050359712230216,
          "profit_factor": 2.867893070291323,
          "pnl_dollars": 384745.8771835808,
          "max_drawdown": -6962.608695884206,
          "avg_pnl": 553.5911901922026,
          "avg_hold_minutes": 120.62589928057554,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.6245988489208634
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.5,
          "profit_factor": 2.3718058294180278,
          "pnl_dollars": 161390.83036851865,
          "max_drawdown": -3527.8450918756307,
          "avg_pnl": 229.9014677614226,
          "avg_hold_minutes": 125.17094017094017,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.6042024216524217
        }
      }
    },
    "option_value_best_select_hard": {
      "overall": {
        "trades": 2099,
        "win_rate": 0.35064316341114815,
        "profit_factor": 2.0043816949736994,
        "pnl_dollars": 633843.9520641583,
        "max_drawdown": -17985.373341995408,
        "avg_pnl": 301.9742506260878,
        "avg_hold_minutes": 96.16484040019057,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.39626684135302526
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.2606837606837607,
          "profit_factor": 1.5958748732395933,
          "pnl_dollars": 121116.16015816206,
          "max_drawdown": -15429.906348767181,
          "avg_pnl": 172.53014267544452,
          "avg_hold_minutes": 80.33475783475784,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.27538874643874645
        },
        "SPX": {
          "trades": 695,
          "win_rate": 0.516546762589928,
          "profit_factor": 2.7607188841213004,
          "pnl_dollars": 405116.7410320949,
          "max_drawdown": -10465.045248089125,
          "avg_pnl": 582.9017856576905,
          "avg_hold_minutes": 123.25179856115108,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.6280618705035971
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.27635327635327633,
          "profit_factor": 1.5442183515544508,
          "pnl_dollars": 107611.05087390142,
          "max_drawdown": -10219.453742410406,
          "avg_pnl": 153.29209526196783,
          "avg_hold_minutes": 85.17806267806267,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.28766125356125355
        }
      }
    },
    "option_value_best_select_learned_exit_5m": {
      "overall": {
        "trades": 2099,
        "win_rate": 0.35874225821819916,
        "profit_factor": 1.872498135181999,
        "pnl_dollars": 543043.9520641584,
        "max_drawdown": -20182.038832849765,
        "avg_pnl": 258.7155560096038,
        "avg_hold_minutes": 87.57265364459266,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.39626684135302526
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.2692307692307692,
          "profit_factor": 1.6373788518339254,
          "pnl_dollars": 128605.16015816206,
          "max_drawdown": -15376.406348767181,
          "avg_pnl": 183.1982338435357,
          "avg_hold_minutes": 77.97720797720798,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.27538874643874645
        },
        "SPX": {
          "trades": 695,
          "win_rate": 0.5338129496402878,
          "profit_factor": 2.4270464786456656,
          "pnl_dollars": 317831.74103209487,
          "max_drawdown": -9840.630884804821,
          "avg_pnl": 457.3118576001365,
          "avg_hold_minutes": 101.17985611510791,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.6280618705035971
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.27492877492877493,
          "profit_factor": 1.488137802023543,
          "pnl_dollars": 96607.05087390142,
          "max_drawdown": -14457.453742410406,
          "avg_pnl": 137.61688158675415,
          "avg_hold_minutes": 83.69658119658119,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.28766125356125355
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 2099,
        "win_rate": 0.5821819914244879,
        "profit_factor": 7.311337166350456,
        "pnl_dollars": 1542132.399826989,
        "max_drawdown": -2333.862270703583,
        "avg_pnl": 734.6986183072839,
        "avg_hold_minutes": 120.23106241067175,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.5226077179609337
      },
      "per_ticker": {
        "QQQ": {
          "trades": 702,
          "win_rate": 0.5754985754985755,
          "profit_factor": 6.231382165875957,
          "pnl_dollars": 444991.9495569266,
          "max_drawdown": -2661.7585440310067,
          "avg_pnl": 633.891666035508,
          "avg_hold_minutes": 121.24643874643874,
          "long_rate": 0.5527065527065527,
          "avg_delta_abs": 0.5254719373219373
        },
        "SPX": {
          "trades": 695,
          "win_rate": 0.5827338129496403,
          "profit_factor": 10.280619463363063,
          "pnl_dollars": 683139.9173558463,
          "max_drawdown": -2431.6993068856536,
          "avg_pnl": 982.9351328861097,
          "avg_hold_minutes": 115.62589928057554,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.5175297841726618
        },
        "SPY": {
          "trades": 702,
          "win_rate": 0.5883190883190883,
          "profit_factor": 5.832396502251918,
          "pnl_dollars": 414000.5329142165,
          "max_drawdown": -2651.541607614141,
          "avg_pnl": 589.7443488806503,
          "avg_hold_minutes": 123.77492877492878,
          "long_rate": 0.5441595441595442,
          "avg_delta_abs": 0.5247707977207977
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 2099,
        "win_rate": 0.9590281086231539,
        "profit_factor": 643.2628454065788,
        "pnl_dollars": 4255387.413006411,
        "max_drawdown": -342.42661216761917,
        "avg_pnl": 2027.3403587453124,
        "avg_hold_minutes": 114.54502143878037,
        "long_rate": 0.549785612196284,
        "avg_delta_abs": 0.38694268699380663
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
          "trades": 695,
          "win_rate": 0.9640287769784173,
          "profit_factor": 866.3919540693034,
          "pnl_dollars": 1625221.3763531896,
          "max_drawdown": -192.13284219556954,
          "avg_pnl": 2338.448023529769,
          "avg_hold_minutes": 120.61151079136691,
          "long_rate": 0.5525179856115108,
          "avg_delta_abs": 0.506719856115108
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
