"""
Aura — Trends Engine
Google Trends data fetching, analysis, and opportunity detection via pytrends.
All calls are rate-limited. Falls back to cached data when blocked.
"""

import json
import random
import time
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import TrendsData, TrendsAlert, Campaign
from utils.logger import get_logger
from config import (
    TRENDS_MAX_KEYWORDS, TRENDS_DEFAULT_TIMEFRAME,
    TRENDS_RATE_LIMIT_BATCH, TRENDS_RATE_LIMIT_SLEEP_MIN,
    TRENDS_RATE_LIMIT_SLEEP_MAX, TRENDS_429_SLEEP,
    TRENDS_CACHE_HOURS, TRENDS_SPIKE_THRESHOLD,
    TRENDS_OPPORTUNITY_MIN_SCORE,
)

logger = get_logger("trends_engine")


class TrendsEngine:
    """Google Trends data fetching and analysis."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._pytrends = None
        self._request_count = 0

    def _get_pytrends(self):
        """Lazy-initialize pytrends client."""
        if self._pytrends is None:
            try:
                from pytrends.request import TrendReq
                self._pytrends = TrendReq(hl="en-US", tz=360)
            except ImportError:
                logger.error("pytrends not installed")
                return None
        return self._pytrends

    def _rate_limit(self):
        """Rate limit pytrends requests."""
        self._request_count += 1
        if self._request_count % TRENDS_RATE_LIMIT_BATCH == 0:
            sleep_time = random.uniform(
                TRENDS_RATE_LIMIT_SLEEP_MIN, TRENDS_RATE_LIMIT_SLEEP_MAX
            )
            logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s after {self._request_count} requests")
            time.sleep(sleep_time)

    def fetch_interest_over_time(self, keywords: list, region: str = "US",
                                  timeframe: str = None) -> dict:
        """Fetch interest-over-time data for up to 5 keywords."""
        keywords = keywords[:TRENDS_MAX_KEYWORDS]
        timeframe = timeframe or TRENDS_DEFAULT_TIMEFRAME

        # Check cache first
        cached = self._get_cached(keywords[0], "interest_over_time", region)
        if cached:
            return cached

        try:
            pt = self._get_pytrends()
            if not pt:
                return {"success": False, "error": "pytrends not available"}

            self._rate_limit()
            pt.build_payload(keywords, geo=region, timeframe=timeframe)
            df = pt.interest_over_time()

            if df is None or df.empty:
                return {"success": True, "data": {"keywords": keywords, "scores": []}}

            # Convert to JSON-serializable format
            scores = {}
            for kw in keywords:
                if kw in df.columns:
                    scores[kw] = [
                        {"date": str(idx.date()), "value": int(row[kw])}
                        for idx, row in df.iterrows()
                        if kw in row.index
                    ]

            # Find peak and current score for the first keyword
            peak_date = None
            current_score = 0
            if keywords[0] in df.columns:
                col = df[keywords[0]]
                if len(col) > 0:
                    peak_idx = col.idxmax()
                    peak_date = str(peak_idx.date()) if peak_idx is not None else None
                    current_score = int(col.iloc[-1]) if len(col) > 0 else 0

            # Detect direction
            direction = self._calculate_direction(df, keywords[0])

            # Store in DB
            self._store_trends_data(
                keyword=keywords[0],
                region=region,
                timeframe=timeframe,
                interest_over_time=json.dumps(scores),
                peak_date=peak_date,
                current_score=current_score,
                trend_direction=direction,
            )

            return {
                "success": True,
                "data": {
                    "keywords": keywords,
                    "region": region,
                    "timeframe": timeframe,
                    "scores": scores,
                    "peak_date": peak_date,
                    "current_score": current_score,
                    "trend_direction": direction,
                },
            }
        except Exception as e:
            if "429" in str(e) or "Too Many" in str(e):
                logger.warning(f"Google Trends rate limited — sleeping {TRENDS_429_SLEEP}s")
                time.sleep(TRENDS_429_SLEEP)
            else:
                logger.error(f"Interest over time fetch failed: {e}")
            # Return cached data if available
            return self._get_cached(keywords[0], "interest_over_time", region) or {
                "success": False, "error": str(e)
            }

    def fetch_related_queries(self, keyword: str, region: str = "US") -> dict:
        """Fetch top and rising related queries for a keyword."""
        cached = self._get_cached(keyword, "related_queries", region)
        if cached:
            return cached

        try:
            pt = self._get_pytrends()
            if not pt:
                return {"success": False, "error": "pytrends not available"}

            self._rate_limit()
            pt.build_payload([keyword], geo=region, timeframe=TRENDS_DEFAULT_TIMEFRAME)
            related = pt.related_queries()

            top = []
            rising = []
            breakouts = []

            if keyword in related and related[keyword] is not None:
                top_df = related[keyword].get("top")
                if top_df is not None and not top_df.empty:
                    top = top_df.to_dict("records")

                rising_df = related[keyword].get("rising")
                if rising_df is not None and not rising_df.empty:
                    for _, row in rising_df.iterrows():
                        entry = {"query": row.get("query", ""), "value": str(row.get("value", ""))}
                        if str(row.get("value", "")).lower() == "breakout":
                            breakouts.append(entry)
                        else:
                            rising.append(entry)

            # Store
            self._store_trends_data(
                keyword=keyword,
                region=region,
                related_queries=json.dumps({"top": top, "rising": rising}),
                rising_breakouts=json.dumps(breakouts),
            )

            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "region": region,
                    "top": top,
                    "rising": rising,
                    "breakouts": breakouts,
                },
            }
        except Exception as e:
            if "429" in str(e):
                time.sleep(TRENDS_429_SLEEP)
            logger.error(f"Related queries fetch failed: {e}")
            return self._get_cached(keyword, "related_queries", region) or {
                "success": False, "error": str(e)
            }

    def fetch_related_topics(self, keyword: str, region: str = "US") -> dict:
        """Fetch related topics for a keyword."""
        try:
            pt = self._get_pytrends()
            if not pt:
                return {"success": False, "error": "pytrends not available"}

            self._rate_limit()
            pt.build_payload([keyword], geo=region, timeframe=TRENDS_DEFAULT_TIMEFRAME)
            topics = pt.related_topics()

            top = []
            rising = []

            if keyword in topics and topics[keyword] is not None:
                top_df = topics[keyword].get("top")
                if top_df is not None and not top_df.empty:
                    top = top_df.to_dict("records")

                rising_df = topics[keyword].get("rising")
                if rising_df is not None and not rising_df.empty:
                    rising = rising_df.to_dict("records")

            # Store
            self._store_trends_data(
                keyword=keyword,
                region=region,
                related_topics=json.dumps({"top": top, "rising": rising}),
            )

            return {
                "success": True,
                "data": {"keyword": keyword, "top": top, "rising": rising},
            }
        except Exception as e:
            logger.error(f"Related topics fetch failed: {e}")
            return {"success": False, "error": str(e)}

    def fetch_interest_by_region(self, keyword: str, region: str = "",
                                  resolution: str = "COUNTRY") -> dict:
        """Fetch geographic interest distribution."""
        try:
            pt = self._get_pytrends()
            if not pt:
                return {"success": False, "error": "pytrends not available"}

            self._rate_limit()
            pt.build_payload([keyword], geo=region, timeframe=TRENDS_DEFAULT_TIMEFRAME)
            df = pt.interest_by_region(resolution=resolution)

            if df is None or df.empty:
                return {"success": True, "data": {"keyword": keyword, "regions": []}}

            regions = []
            for idx, row in df.iterrows():
                val = int(row[keyword]) if keyword in row.index else 0
                if val > 0:
                    regions.append({"region": str(idx), "value": val})

            regions.sort(key=lambda x: x["value"], reverse=True)

            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "resolution": resolution,
                    "regions": regions[:50],
                },
            }
        except Exception as e:
            logger.error(f"Interest by region failed: {e}")
            return {"success": False, "error": str(e)}

    def compare_keywords(self, keywords: list, region: str = "US",
                          timeframe: str = None) -> dict:
        """Compare multiple keywords' interest over time."""
        return self.fetch_interest_over_time(
            keywords[:TRENDS_MAX_KEYWORDS], region, timeframe
        )

    def detect_trend_direction(self, keyword: str, region: str = "US") -> dict:
        """Analyze whether a keyword is rising, stable, or declining."""
        result = self.fetch_interest_over_time(
            [keyword], region, "today 3-m"
        )
        if not result.get("success"):
            return result

        direction = result["data"].get("trend_direction", "stable")
        return {
            "success": True,
            "data": {
                "keyword": keyword,
                "region": region,
                "direction": direction,
                "current_score": result["data"].get("current_score", 0),
            },
        }

    def find_opportunity_niches(self, seed_keywords: list,
                                 region: str = "US") -> dict:
        """Discover rising niches not yet targeted by any active campaign."""
        try:
            opportunities = []

            # Get existing campaign niches
            with self.db_manager.session_scope() as session:
                campaigns = session.query(Campaign).filter(
                    Campaign.status.in_(["active", "draft"])
                ).all()
                existing_niches = {
                    c.target_niche.lower() for c in campaigns if c.target_niche
                }

            for kw in seed_keywords[:3]:  # Limit to avoid rate limits
                related = self.fetch_related_queries(kw, region)
                if not related.get("success"):
                    continue

                data = related.get("data", {})

                # Check rising queries
                for item in data.get("rising", []) + data.get("breakouts", []):
                    query = item.get("query", "")
                    value = str(item.get("value", "0"))

                    if not query or query.lower() in existing_niches:
                        continue

                    try:
                        score = int(value) if value.isdigit() else 100
                    except (ValueError, TypeError):
                        score = 100  # Breakout

                    if score >= TRENDS_OPPORTUNITY_MIN_SCORE:
                        is_breakout = value.lower() == "breakout" or score >= 5000
                        opportunities.append({
                            "niche": query,
                            "region": region,
                            "trend_score": min(score, 100) if not is_breakout else 100,
                            "direction": "breakout" if is_breakout else "rising",
                            "source_keyword": kw,
                            "reason": (
                                f"Breakout trend from '{kw}'"
                                if is_breakout
                                else f"Rising {score}% from '{kw}'"
                            ),
                        })

            # Deduplicate by niche name
            seen = set()
            unique = []
            for opp in opportunities:
                key = opp["niche"].lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(opp)

            unique.sort(key=lambda x: x["trend_score"], reverse=True)

            return {
                "success": True,
                "data": {"opportunities": unique[:20], "region": region},
            }
        except Exception as e:
            logger.error(f"Opportunity discovery failed: {e}")
            return {"success": False, "error": str(e)}

    def monitor_campaign_keywords(self, campaign_id: int) -> dict:
        """Check trend status for keywords associated with a campaign."""
        try:
            with self.db_manager.session_scope() as session:
                campaign = session.query(Campaign).filter_by(id=campaign_id).first()
                if not campaign:
                    return {"success": False, "error": f"Campaign {campaign_id} not found"}
                niche = campaign.target_niche or ""
                city = campaign.target_city or ""
                name = campaign.name

            if not niche:
                return {"success": False, "error": "Campaign has no target niche"}

            keywords = [niche]
            if city:
                keywords.insert(0, f"{niche} {city}")

            result = self.fetch_interest_over_time(keywords, timeframe="today 3-m")
            if not result.get("success"):
                return result

            data = result.get("data", {})
            direction = data.get("trend_direction", "stable")
            current_score = data.get("current_score", 0)

            # Check for significant changes and create alert
            last_data = self._get_last_stored(niche)
            if last_data:
                last_score = last_data.get("current_score", 0)
                change = abs(current_score - last_score)
                if change >= TRENDS_SPIKE_THRESHOLD:
                    alert_type = "spike" if current_score > last_score else "seasonal"
                    self._create_alert(
                        keyword=niche,
                        alert_type=alert_type,
                        message=(
                            f"'{niche}' trend score changed by {change} points "
                            f"({last_score} → {current_score}) for campaign '{name}'"
                        ),
                        campaign_id=campaign_id,
                    )

            return {
                "success": True,
                "data": {
                    "campaign_id": campaign_id,
                    "campaign_name": name,
                    "niche": niche,
                    "city": city,
                    "direction": direction,
                    "current_score": current_score,
                    "keywords_checked": keywords,
                },
            }
        except Exception as e:
            logger.error(f"Campaign monitoring failed: {e}")
            return {"success": False, "error": str(e)}

    def schedule_trend_checks(self) -> dict:
        """Run trend checks for all active campaigns."""
        try:
            with self.db_manager.session_scope() as session:
                campaigns = session.query(Campaign).filter_by(status="active").all()
                campaign_ids = [c.id for c in campaigns]

            results = []
            for cid in campaign_ids:
                r = self.monitor_campaign_keywords(cid)
                results.append(r)

            return {
                "success": True,
                "data": {
                    "campaigns_checked": len(campaign_ids),
                    "results": results,
                },
            }
        except Exception as e:
            logger.error(f"Scheduled trend checks failed: {e}")
            return {"success": False, "error": str(e)}

    def get_alerts(self, unread_only: bool = True, limit: int = 50) -> dict:
        """Retrieve trend alerts."""
        try:
            with self.db_manager.session_scope() as session:
                q = session.query(TrendsAlert)
                if unread_only:
                    q = q.filter_by(acknowledged=False)
                alerts = (
                    q.order_by(TrendsAlert.triggered_at.desc())
                    .limit(limit)
                    .all()
                )

                result = []
                for a in alerts:
                    result.append({
                        "id": a.id,
                        "keyword": a.keyword,
                        "alert_type": a.alert_type,
                        "message": a.message,
                        "acknowledged": a.acknowledged,
                        "triggered_at": (
                            a.triggered_at.isoformat() if a.triggered_at else None
                        ),
                        "campaign_id": a.campaign_id,
                    })

            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def acknowledge_alert(self, alert_id: int) -> dict:
        """Mark an alert as acknowledged."""
        try:
            with self.db_manager.session_scope() as session:
                alert = session.query(TrendsAlert).filter_by(id=alert_id).first()
                if alert:
                    alert.acknowledged = True
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Internal helpers ──────────────────────────────────────────────

    def _calculate_direction(self, df, keyword: str) -> str:
        """Calculate trend direction from a DataFrame."""
        try:
            if keyword not in df.columns or len(df) < 14:
                return "stable"

            col = df[keyword]
            recent = col.iloc[-7:].mean()
            earlier = col.iloc[-90:-60].mean() if len(col) >= 90 else col.iloc[:7].mean()

            if earlier == 0:
                return "rising" if recent > 10 else "stable"

            ratio = recent / earlier
            if ratio > 2.0:
                return "breakout"
            elif ratio > 1.3:
                return "rising"
            elif ratio < 0.7:
                return "falling"
            return "stable"
        except Exception:
            return "stable"

    def _store_trends_data(self, keyword: str, region: str = "US",
                           timeframe: str = None, **kwargs):
        """Store trends data in the DB."""
        try:
            with self.db_manager.session_scope() as session:
                td = TrendsData(
                    keyword=keyword,
                    region=region,
                    timeframe=timeframe or TRENDS_DEFAULT_TIMEFRAME,
                    interest_over_time=kwargs.get("interest_over_time", "{}"),
                    related_queries=kwargs.get("related_queries", "{}"),
                    related_topics=kwargs.get("related_topics", "{}"),
                    rising_breakouts=kwargs.get("rising_breakouts", "{}"),
                    peak_date=kwargs.get("peak_date"),
                    current_score=kwargs.get("current_score", 0),
                    trend_direction=kwargs.get("trend_direction"),
                    fetched_at=datetime.utcnow(),
                    campaign_id=kwargs.get("campaign_id"),
                )
                session.add(td)
        except Exception as e:
            logger.error(f"Failed to store trends data: {e}")

    def _get_cached(self, keyword: str, data_type: str,
                    region: str = "US") -> dict:
        """Check for recent cached data."""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=TRENDS_CACHE_HOURS)
            with self.db_manager.session_scope() as session:
                td = (
                    session.query(TrendsData)
                    .filter(
                        TrendsData.keyword == keyword,
                        TrendsData.region == region,
                        TrendsData.fetched_at > cutoff,
                    )
                    .order_by(TrendsData.fetched_at.desc())
                    .first()
                )
                if not td:
                    return None

                if data_type == "interest_over_time" and td.interest_over_time != "{}":
                    return {
                        "success": True,
                        "cached": True,
                        "data": {
                            "keywords": [keyword],
                            "region": region,
                            "scores": json.loads(td.interest_over_time),
                            "peak_date": td.peak_date,
                            "current_score": td.current_score or 0,
                            "trend_direction": td.trend_direction or "stable",
                        },
                    }
                elif data_type == "related_queries" and td.related_queries != "{}":
                    rq = json.loads(td.related_queries)
                    rb = json.loads(td.rising_breakouts) if td.rising_breakouts else []
                    return {
                        "success": True,
                        "cached": True,
                        "data": {
                            "keyword": keyword,
                            "region": region,
                            "top": rq.get("top", []),
                            "rising": rq.get("rising", []),
                            "breakouts": rb,
                        },
                    }
        except Exception:
            pass
        return None

    def _get_last_stored(self, keyword: str) -> dict:
        """Get the last stored data for comparison."""
        try:
            with self.db_manager.session_scope() as session:
                td = (
                    session.query(TrendsData)
                    .filter_by(keyword=keyword)
                    .order_by(TrendsData.fetched_at.desc())
                    .first()
                )
                if td:
                    return {
                        "current_score": td.current_score or 0,
                        "trend_direction": td.trend_direction,
                    }
        except Exception:
            pass
        return None

    def _create_alert(self, keyword: str, alert_type: str, message: str,
                      campaign_id: int = None):
        """Create a trend alert."""
        try:
            with self.db_manager.session_scope() as session:
                alert = TrendsAlert(
                    keyword=keyword,
                    alert_type=alert_type,
                    message=message,
                    campaign_id=campaign_id,
                    triggered_at=datetime.utcnow(),
                )
                session.add(alert)
            logger.info(f"Trends alert: [{alert_type}] {message}")
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
