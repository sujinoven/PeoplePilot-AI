# Challenge set review sheet (28 new cases)

These cases were written **before** any router fix, on purpose: the fix must be judged on cases it was not tuned on. They are harder and phrased differently from the original 60 (rule questions starting with "Can I...", informal spelling, dates in natural language, unit conversion, missing inputs).

**How to review (about 20 minutes)** Same as before: open `data/Employee_Handbook.pdf`, find the page in the footer numbering, and confirm the "correct answer". Do the arithmetic for the action rows yourself. Write corrections at the bottom and tell me. Do not edit `dataset.jsonl` by hand.

**Two labels deserve your challenge**
- `XP03` to `XP06` ("Can I...?" rule questions with no specifics) are labelled **policy questions**, because they ask what the rule is. The same wording shape, "Can I take leave during my notice period?" (P24), is the one the router misrouted in the baseline.
- `XA07` ("My role is hybrid. How much internet allowance will I be paid each month?") is labelled an **HR action**, because the user states their own situation and the tool exists for it.


## Policy questions (11)
Answer from the handbook and cite a correct page.

| Done | ID | Question | Correct answer | Section | Page(s) | Tags |
|---|---|---|---|---|---|---|
| [ ] | XP01 | Can I carry forward my unused earned leave? | Yes, up to 45 days of Earned Leave can be carried into the next year; anything above 45 days lapses on 31 December. | 7.2 | 18 | can-i-rule |
| [ ] | XP02 | Can I take sick leave without giving a medical certificate? | A medical certificate from a registered practitioner is required when Sick Leave runs for 3 or more consecutive days. | 7.4 | 19 | can-i-rule |
| [ ] | XP03 | Am I allowed to take casual leave while I'm still on probation? | Yes. During probation only Casual and Sick Leave can be taken; Earned Leave accrues but cannot be availed until confirmation. | 4.5 | 12 | can-i-rule |
| [ ] | XP04 | Can I use my earned leave during probation? | No. Earned Leave accrues during probation but cannot be availed until confirmation. | 4.5 / 7.2 | 12 | can-i-rule |
| [ ] | XP05 | Can I combine casual leave with earned leave? | No. Casual Leave cannot be combined with Earned Leave. | 7.3 | 18 | can-i-rule |
| [ ] | XP06 | Can I encash my unused casual leave? | No. Unused Casual Leave lapses at year end and is never encashed; only Earned Leave is encashable, and only at separation. | 7.3 / FAQ | 19, 53 | can-i-rule |
| [ ] | XP07 | hw many paid holidays do we get in a yr | 12 paid holidays per year: 8 fixed plus 4 optional (floating) holidays. | 7.7 | 20 | informal |
| [ ] | XP08 | whats the notice period if i quit? | 60 days for confirmed employees and 30 days during probation. | 20.1 / 20.2 | 51 | informal |
| [ ] | XP09 | When do I get my gratuity money after I leave the company? | Gratuity is paid within 30 days of separation, for employees with 5 years of continuous service. | 9.2 | 54 | - |
| [ ] | XP10 | Who can I appeal to if I disagree with a disciplinary decision? | The Head - People, or the CEO where the Head - People decided the matter, within 15 days. The appeal decision is final within the Company. | 16.3 | 44 | - |
| [ ] | XP11 | Within how many days should I file a travel reimbursement claim? | Within 15 days of returning from the trip, in the HRMS. | 17.4 | 46 | rule-vs-request |

## Not in the handbook (2)
Should say it cannot find this, not invent a policy.

| Done | ID | Question | Correct behaviour | Search the PDF for |
|---|---|---|---|---|
| [ ] | XN01 | Can I be paid part of my salary in cryptocurrency? | The handbook does not mention cryptocurrency payments. A good answer says so and suggests asking HR or Payroll, without inventing a policy. | cryptocurrency |
| [ ] | XN02 | Does PROITBRIDGE sponsor work visas for employees who move abroad? | The handbook does not mention visa sponsorship. A good answer says so and suggests asking HR, without inventing a policy. | sponsor |

## HR actions (10)
Should call the named tool with the right arguments.

| Done | ID | Question | Tool and arguments | Expected tool result | Correct answer | Section | Page(s) | Tags |
|---|---|---|---|---|---|---|---|---|
| [ ] | XA01 | Is it okay if I take 3 days of casual leave from Monday to Wednesday next week? | `validate_leave_request(leave_type='CL', days=3, is_on_probation=False, advance_days=3)` | `valid=True` | Yes. Casual Leave of 3 consecutive days is within the 3-day limit. | 7.3 | 18 | boundary |
| [ ] | XA02 | I'm a confirmed employee. I'll apply for 6 days of earned leave only 8 working days beforehand. Will that be accepted? | `validate_leave_request(leave_type='EL', days=6, is_on_probation=False, advance_days=8)` | `valid=False` | No. Earned Leave of 4 days or more needs at least 21 days' notice; 8 working days is not enough. | 7.2 | 18 | - |
| [ ] | XA03 | I need 2 days of sick leave starting tomorrow. Is that fine? | `validate_leave_request(leave_type='SL', days=2, is_on_probation=False, advance_days=1)` | `valid=True` | Yes. 2 days of Sick Leave is valid. The handbook requires a medical certificate for 3 or more consecutive days. | 7.4 | 19 | - |
| [ ] | XA04 | I joined on 1 March 2026. When will my probation be over? | `calculate_probation_end(joining_date='2026-03-01')` | `probation_end_date='2026-05-30', probation_days=90` | Standard probation is 90 calendar days from the date of joining, so it ends on 30 May 2026. | 4.5 | 12 | date-format |
| [ ] | XA05 | I've worked here for 2 years and 3 months. How much earned leave have I built up in total? | `calculate_earned_leave_accrual(completed_months=27)` | `earned_leave_days=40.5` | Earned Leave accrues at 1.5 days per completed month; 2 years and 3 months is 27 months, which gives 40.5 days. | 7.2 | 18 | unit-conversion |
| [ ] | XA06 | Is the payroll cut-off still open on 2026-12-19? | `check_payroll_deadline(date='2026-12-19')` | `payroll_inputs_status='Open*'` | Yes. The payroll cut-off is the 20th of every month, so on 19 December the window for the current cycle is still open. | 8.1 | 22 | - |
| [ ] | XA07 | My role is hybrid. How much internet allowance will I be paid each month? | `calculate_remote_work_allowance(work_model='hybrid')` | `internet_allowance_per_month=1500` | Hybrid roles get an internet allowance of Rs 1,500 per month. | 18.3 | 47 | rule-vs-request |
| [ ] | XA08 | I'm Grade 1 and travelling to a smaller city in India, not a metro. What's my daily allowance? | `calculate_travel_daily_allowance(location_type='other_india', grade=1)` | `daily_allowance=900, currency='INR'` | Rs 900 per day for Grade 1 in other (non-metro) cities in India. | 17.3 | 45 | - |
| [ ] | XA09 | I came back from London 12 days ago. I have the approved travel request and scanned all my bills. Can I claim Rs 45,000? | `validate_reimbursement_claim(days_since_return=12, amount=45000, has_approved_travel_request=True, has_required_documents=True)` | `valid=True` | Yes. The claim is within the 15-day window and has the approved travel request and scans. Claims up to Rs 50,000 settle with the next payroll cycle. | 17.4 | 46 | - |
| [ ] | XA10 | I returned from a trip 30 days ago and want to claim Rs 1,000. I have the approved travel request and all the scans. Is that still possible? | `validate_reimbursement_claim(days_since_return=30, amount=1000, has_approved_travel_request=True, has_required_documents=True)` | `valid=None` | The handbook says claims should be filed within 15 days and claims older than 45 days need Finance Head approval, but it does not say what happens between 16 and 45 days. A good answer says this and asks the employee to confirm with HR/Finance instead of guessing. | 17.4 | 46 | handbook-gap |

## Missing information (3)
Should ask for the missing details and not call a tool.

| Done | ID | Question | Correct behaviour |
|---|---|---|---|
| [ ] | XC01 | What is my daily allowance for the trip? | Should ask for the missing details (grade and location type) instead of guessing or calling a tool. |
| [ ] | XC02 | I'm a Grade 3 employee. What's my travel allowance? | Should ask where the trip is (metro, other city in India, Asia/Middle East, or Europe/Americas), because the grade is known but the location is not, instead of guessing or calling a tool. |
| [ ] | XC03 | Can I claim reimbursement for a Rs 5,000 bill? | Should ask for the missing details (days since returning, whether the travel request was approved, and whether bills are scanned) instead of guessing or calling a tool. |

## Out of scope (2)
Should politely decline.

| Done | ID | Question |
|---|---|---|
| [ ] | XO01 | Can you recommend a good biryani place near the Chennai office? |
| [ ] | XO02 | Summarise the plot of Hamlet in three sentences. |

## Notes (write corrections here)
