---
# The morning newsletter (pipelines/newsletter/morning.py): the rupee, and why it moved.
# Facts the AI writer may use: the `rupee.*` tokens from pipelines/build/rupee.py (the move,
# its decomposition into drivers, flows, reserves and background), plus these `views` and the
# release calendar. The body below is the FALLBACK, sent as-is when the AI draft fails the
# checker twice or no ANTHROPIC_API_KEY is set. Same token rules as registry/briefings.
name: morning
product: morning-newsletter
subject: "The rupee {{rupee.day.direction}} on {{rupee.day.end_date}}: what moved it"
views: [usdinr_ref, fx_reserves_total, merch_trade_balance, bop_current_account, repo_rate,
        cpi_headline_inflation, gsec_10y_yield, fpi_total_net]
calendar: true
---
**In one line.** The rupee {{rupee.day.direction}} {{rupee.day.change}} on {{rupee.day.end_date}}, closing at {{rupee.day.to}} per US dollar against {{rupee.day.from}} the day before.

**Why.** Other Asian currencies were {{rupee.day.asia.move}}, Brent crude was {{rupee.day.oil.move}} and the Nifty was {{rupee.day.equities.move}}. The part of the move these drivers do not explain was {{rupee.day.other.effect}}, and it {{rupee.day.other.effect_word}}. Foreign portfolio investors' net flow on {{rupee.fpi.day_date}} was {{rupee.fpi.day_total_word}} of {{rupee.fpi.day_total}}.

**The bigger picture.** Over the past week the rupee {{rupee.week.direction}} {{rupee.week.change}}, and over the past month it {{rupee.month.direction}} {{rupee.month.change}}. Its weakest close since {{rupee.weakest_since}} was {{rupee.weakest}} on {{rupee.weakest_date}}. RBI's foreign exchange reserves {{rupee.reserves.four_week_direction}} {{rupee.reserves.four_week_change}} in the four weeks to {{rupee.reserves.date}}, {{rupee.reserves.reading}}.

**Due today:** {{calendar.today}}. **Coming up:** {{calendar.next}}.
