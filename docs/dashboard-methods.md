# Dashboard methods

How the dashboard answers each question, and the limits of the data behind it.

## Growth: two methods (toggle "Growth method")

- **Same project (default).** A repeat-sales index. The repeat unit is a *project's size band*: project × bedroom band for apartments, condos and ECs, and project × property type for landed homes. For every unit, each pair of consecutive periods in which it traded gives a log change in its median $psf (or price). One log level per period is then fitted to all those changes by weighted least squares (Bailey–Muth–Nourse), with weights √min(n₁, n₂) and changes clipped at ±0.7. A tiny smoothness penalty only bridges periods that no unit connects. A wave of new launches, or a shift in which projects sell, therefore doesn't show up as growth. This method always uses medians.
- **All transactions.** The chosen statistic (median, mean, lowest or highest) of everything that sold in the first period versus the last.
- **Both methods:** CAGR = (last ÷ first)^(1/years) − 1, with the two anchor periods at least 1 year apart. Total growth is the same ratio, not annualised. Periods only partly covered by the data (such as the current quarter) aren't used as anchors unless nothing else is available.
- **Why it matters.** CAGR of $psf from 2021 Q4 to 2026 Q3, as computed by the dashboard on the archive as of 19 Oct 2026:

  | Selection | Method | CCR | RCR | OCR |
  |---|---|---|---|---|
  | All private homes | Same project | 2.1% | 4.0% | 5.4% |
  | All private homes | All transactions | 2.0% | 3.7% | 6.5% |
  | 3-bed band, non-landed | Same project | 2.4% | 3.8% | 5.2% |
  | 3-bed band, non-landed | All transactions | 4.8% | 4.9% | 7.3% |

  Counting every transaction overstates growth wherever new launches, which are pricier per sq ft, make up a growing share of sales.
- **$psf versus price.** $psf is the cleaner like-for-like measure. Price growth within a band can also reflect bigger or smaller units selling.

## Lease stage ("Lease stage" tab)

Each project is placed in a band by its remaining lease at the *start* of the time range: freehold, 999-yr, 95+, 90–95, 85–90, 80–85, 70–80, 60–70 or under 60 years. The band's growth is the same-project index over the range. It answers "if I'd bought at this stage of the lease, how did those homes move?". The *Repeat obs.* column shows how many same-project price changes each figure rests on.

## Floor level ("Floor level" tab)

The premium versus floors 01–05 is the median, across project size bands that trade in both floor bands, of (median $psf in the band ÷ median $psf at 01–05) − 1. Velocity is transactions per year. URA doesn't publish how many units sit on each floor, so this shows where trading happens, not a turnover rate.

## Sale lifecycle ("Sale lifecycle" tab)

- **By sale type:** new sale, sub sale and resale.
- **By lease age:** $psf by years since the lease began (leasehold only), split by sale type.
- **Premium over own launch price:** for each sub sale or resale, its $psf ÷ the same project size band's median new-sale $psf over the whole archive, minus 1. These are grouped by years since that band first sold. This table only covers launches that are inside the archive (from Oct 2021), so it fills in over time.

## Bedrooms (filter "Unit size ≈ bedrooms")

URA doesn't record bedrooms, so the filter uses size bands for apartments, condos and ECs. The defaults come from where new-launch unit sizes cluster in the data:

| Band | Size (sq ft) |
|---|---|
| Studio / 1-bed | under 580 |
| 2-bed | 580–849 |
| 3-bed | 850–1,199 |
| 4-bed | 1,200–1,599 |
| 5-bed+ / penthouse | 1,600 and above |

The cut-offs can be edited on the page and are remembered in the browser. Picking a subset hides landed homes. Older condos are larger for the same bedroom count.

## Harmonised floor areas (filter "Floor-area basis")

URA circular URA/PB/2022/09-DCG covers development applications from 1 Jun 2023 and government land sale sites launched from 1 Sep 2022. Under it, voids are excluded and areas are measured to the middle of the wall, so listed areas are smaller and $psf is higher for the same space. URA's transaction data has no flag for this, so `data/harmonisation.json` holds:

- **Confirmed projects:** Lentor Mansion, Emerald of Katong, Norwood Grand, Parktown Residence and ELTA, each with a source.
- **A rule** that marks other projects as *likely*: a leasehold project whose lease began in 2023 or later and which first sold in Mar 2024 or later. This currently catches 37 more projects.
- **Override lists** for forcing a project in or out.

The filter shows pre-harmonisation projects, harmonised projects, or both. The *gross-up %* setting (off by default; industry estimates are about 4–5%) multiplies harmonised areas by (1 + x%) to put them on the old basis. That changes their $psf and their size band.

## Rentals ("Rentals" tab, map metrics "Median rent" and "Gross rental yield")

URA publishes median rent per sq ft per month for each non-landed project and quarter, with no contract counts. Figures for a district, segment or property type are medians of the project medians for the latest quarter in range. Gross yield = rent × 12 ÷ median resale $psf of the same scope over the last four quarters, using non-landed resales under the current filters.

## Pinned comparison

You can pin up to 8 items: the whole island, a segment, a district or a project. Each keeps its colour for as long as it stays pinned, and pins are saved in the browser. The panel has a chart (index of $psf or price rebased to 100, $psf, price, transactions, or rent) and a table of merits. The best value among the pins is highlighted for growth, yield and velocity. Every figure uses the page's current filters, time range, statistic and growth method.
