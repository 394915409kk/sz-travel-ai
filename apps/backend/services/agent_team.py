import json
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class ProductDestination(Enum):
    """Supported product destinations for specialized analytics"""
    SAIPAN = "saipan"
    PHU_QUOC = "phu_quoc"
    HK_MACAU = "hk_macau"
    OTHER = "other"


@dataclass
class Agent:
    """Base Agent definition"""
    name: str
    role: str
    expertise: str

    def __repr__(self):
        return f"{self.name} ({self.role})"


class MarketStrategist(Agent):
    """Analyzes market trends and competitive positioning"""

    def __init__(self):
        super().__init__(
            name="Market Strategist",
            role="Market Analysis & Positioning",
            expertise="Market trends, competitive analysis, pricing strategy"
        )

    async def analyze(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market positioning and strategy
        """
        destination = product_data.get("destination", "").lower()
        price = product_data.get("price", "")
        title = product_data.get("title", "")

        analysis = {
            "agent": self.name,
            "market_segment": self._identify_market_segment(destination),
            "positioning": self._generate_positioning(destination, price),
            "competitive_edge": self._analyze_competitive_advantage(destination),
            "pricing_strategy": self._analyze_pricing(destination, price),
            "target_season": self._identify_target_season(destination)
        }

        return analysis

    def _identify_market_segment(self, destination: str) -> str:
        """Identify market segment based on destination"""
        segments = {
            "saipan": "Luxury leisure travel, family vacations, honeymoon destination",
            "phu_quoc": "Budget-friendly beach getaway, backpacker haven, emerging tourist hub",
            "hk": "Urban luxury shopping, business travel, cultural exploration",
            "macau": "Gaming tourism, luxury retail, cultural heritage experiences",
        }
        return segments.get(destination, "General leisure travel")

    def _generate_positioning(self, destination: str, price: str) -> str:
        """Generate market positioning statement"""
        if destination == "saipan":
            return "Premium island destination with exclusive flight packages, positioned as top choice for US-bound luxury travelers"
        elif destination == "phu_quoc":
            return "Value-focused beach paradise, ideal for cost-conscious travelers seeking authentic Southeast Asian experiences"
        elif destination in ["hk", "macau"]:
            return "Urban luxury hub combining shopping, dining, and entertainment for affluent Asian travelers"
        return "Competitive leisure destination with strong market appeal"

    def _analyze_competitive_advantage(self, destination: str) -> List[str]:
        """Identify competitive advantages"""
        if destination == "saipan":
            return [
                "Direct HX flights (HX072/HX073) - exclusive routing",
                "All-inclusive packages (flight + hotel bundled)",
                "US-adjacent location attracts American tourists",
                "Pearl Harbor proximity adds historical value"
            ]
        elif destination == "phu_quoc":
            return [
                "Emerging destination with lower prices",
                "Pristine beaches less crowded than Thailand",
                "Vietnamese cuisine and culture authenticity",
                "Growing infrastructure and amenities"
            ]
        return ["Unique experiences", "Competitive pricing", "Accessibility"]

    def _analyze_pricing(self, destination: str, price: str) -> Dict[str, Any]:
        """Analyze pricing strategy"""
        if destination == "saipan":
            return {
                "strategy": "Premium pricing model",
                "base_price": "4999元起",
                "value_prop": "包含往返机票和酒店 (Flight + Hotel)",
                "recommendation": "Maintain premium positioning, justify with exclusivity"
            }
        return {
            "strategy": "Market-competitive pricing",
            "base_price": price or "Market-dependent",
            "recommendation": "Monitor competitor pricing and adjust quarterly"
        }

    def _identify_target_season(self, destination: str) -> Dict[str, str]:
        """Identify optimal travel seasons"""
        if destination == "saipan":
            return {
                "peak": "November-March (dry season, peak tourism)",
                "secondary": "May-June (pre-typhoon season)",
                "lowest": "July-October (typhoon season)"
            }
        elif destination == "phu_quoc":
            return {
                "peak": "November-April (dry season)",
                "secondary": "May-August (some rain, fewer tourists)",
                "lowest": "September-October (monsoon season)"
            }
        return {"peak": "Year-round", "secondary": "varies", "lowest": "varies"}


class PersonaExpert(Agent):
    """Develops target audience personas and segmentation"""

    def __init__(self):
        super().__init__(
            name="Persona Expert",
            role="Target Audience & Segmentation",
            expertise="Persona development, audience psychology, segmentation strategy"
        )

    async def analyze(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Develop personas and audience segmentation
        """
        destination = product_data.get("destination", "").lower()
        price = product_data.get("price", "")

        personas = self._generate_personas(destination, price)

        analysis = {
            "agent": self.name,
            "primary_personas": personas,
            "audience_psychology": self._analyze_audience_psychology(destination),
            "decision_drivers": self._identify_decision_drivers(destination),
            "pain_points": self._identify_pain_points(destination),
            "value_triggers": self._identify_value_triggers(destination)
        }

        return analysis

    def _generate_personas(self, destination: str, price: str) -> List[Dict[str, Any]]:
        """Generate target personas based on destination"""
        if destination == "saipan":
            return [
                {
                    "name": "Luxury Family Traveler",
                    "age_range": "35-55",
                    "income": "500K+RMB",
                    "motivation": "Family bonding, safety, convenience",
                    "characteristics": "High disposable income, values convenience, willing to pay premium"
                },
                {
                    "name": "Honeymoon Seeker",
                    "age_range": "25-35",
                    "income": "300K+RMB",
                    "motivation": "Romance, exclusive experience, Instagram-worthy",
                    "characteristics": "Seeks unique experiences, shares on social media, willing to invest in memories"
                },
                {
                    "name": "US-Connection Business Traveler",
                    "age_range": "30-50",
                    "income": "400K+RMB",
                    "motivation": "Convenience, direct flights, business efficiency",
                    "characteristics": "Values time, seeks direct routing, includes family leisure"
                }
            ]
        elif destination == "phu_quoc":
            return [
                {
                    "name": "Budget-Conscious Explorer",
                    "age_range": "20-35",
                    "income": "100K-300KRMB",
                    "motivation": "Authentic experiences, value for money",
                    "characteristics": "Seeks emerging destinations, flexible dates, group travel"
                },
                {
                    "name": "Beach Escape Seeker",
                    "age_range": "30-50",
                    "income": "200K-500KRMB",
                    "motivation": "Relaxation, quality time with family",
                    "characteristics": "Seeks less crowded beaches, good dining, family-friendly"
                }
            ]
        return [{"name": "General Traveler", "age_range": "20-60", "motivation": "Travel and exploration"}]

    def _analyze_audience_psychology(self, destination: str) -> Dict[str, str]:
        """Analyze psychological aspects of target audience"""
        if destination == "saipan":
            return {
                "aspiration": "Luxury lifestyle signaling, international prestige",
                "security": "Trust in brand, premium service guarantees",
                "belonging": "Exclusive traveler community, VIP status"
            }
        elif destination == "phu_quoc":
            return {
                "aspiration": "Adventure, discovery of hidden gems",
                "security": "Authentic recommendations, trusted platforms",
                "belonging": "Traveler community sharing authentic experiences"
            }
        return {"aspiration": "Exploration", "security": "Trust", "belonging": "Community"}

    def _identify_decision_drivers(self, destination: str) -> List[str]:
        """Identify key factors influencing purchase decision"""
        if destination == "saipan":
            return [
                "Direct flights availability (HX072/HX073)",
                "All-inclusive package value (flight + hotel)",
                "Premium pricing reflecting exclusivity",
                "Safety and political stability",
                "Family-friendly infrastructure"
            ]
        return ["Price", "Convenience", "Recommendations", "Reviews", "Timing"]

    def _identify_pain_points(self, destination: str) -> List[str]:
        """Identify customer pain points"""
        if destination == "saipan":
            return [
                "High flight costs without bundling",
                "Limited accommodation options at premium level",
                "Visa requirements complexity",
                "Limited direct flight options from other cities"
            ]
        elif destination == "phu_quoc":
            return [
                "Infrastructure still developing",
                "Language barriers for non-Vietnamese speakers",
                "Seasonal weather unpredictability",
                "Limited high-end accommodation"
            ]
        return ["Cost", "Time", "Accessibility", "Information"]

    def _identify_value_triggers(self, destination: str) -> List[str]:
        """Identify value triggers for purchasing"""
        if destination == "saipan":
            return [
                "Direct flight convenience",
                "All-inclusive pricing transparency",
                "Luxury hotel partnerships",
                "Exclusive Saipan experiences",
                "Safety guarantees and travel insurance"
            ]
        return ["Best price", "Quality", "Convenience", "Trust", "Community"]


class CopywritingMaster(Agent):
    """Crafts compelling marketing messaging and copy"""

    def __init__(self):
        super().__init__(
            name="Copywriting Master",
            role="Marketing Messaging & Creative Copy",
            expertise="Persuasive copywriting, messaging strategy, emotional engagement"
        )

    async def analyze(self, product_data: Dict[str, Any], market_analysis: Dict[str, Any], personas: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate marketing copy and messaging strategy
        """
        destination = product_data.get("destination", "").lower()
        price = product_data.get("price", "")
        title = product_data.get("title", "")

        copy = {
            "agent": self.name,
            "primary_headline": self._generate_headline(destination, title),
            "subheadline": self._generate_subheadline(destination),
            "value_proposition": self._generate_value_proposition(destination, price),
            "emotional_appeal": self._craft_emotional_appeal(destination),
            "call_to_action": self._generate_cta(destination),
            "key_messages": self._generate_key_messages(destination),
            "social_media_hooks": self._generate_social_hooks(destination),
            "email_subject_variants": self._generate_email_subjects(destination)
        }

        return copy

    def _generate_headline(self, destination: str, title: str) -> str:
        """Generate primary headline"""
        if destination == "saipan":
            return "独家HX直飞：4999元起，马里亚纳海沟邂逅太平洋奢华" or title
        elif destination == "phu_quoc":
            return "珍珠岛屿秘境：未被发现的越南天堂，这次真的值回票价"
        elif destination in ["hk", "macau"]:
            return "东方之珠：购物、美食、文化，一站式奢华体验"
        return f"探索 {title}：您的终极旅行体验"

    def _generate_subheadline(self, destination: str) -> str:
        """Generate subheadline"""
        if destination == "saipan":
            return "直达班次HX072/HX073，航班+酒店打包价，安心出游0烦恼"
        elif destination == "phu_quoc":
            return "避开人山人海，发现真正的东南亚原生态美景"
        elif destination in ["hk", "macau"]:
            return "品尝米其林美食，畅享国际品牌购物，感受东西方文化碰撞"
        return "探索独特的文化与自然风景"

    def _generate_value_proposition(self, destination: str, price: str) -> str:
        """Generate value proposition statement"""
        if destination == "saipan":
            return (
                f"一价全包：{price}\n"
                "✓ 往返直航班机（HX072/HX073）\n"
                "✓ 精选五星酒店住宿\n"
                "✓ 24小时中文客服支持\n"
                "✓ 签证协助与旅游保险\n"
                "✓ 专享行程规划服务"
            )
        elif destination == "phu_quoc":
            return (
                "度假从简单开始：\n"
                "✓ 竞争力价格与优质服务\n"
                "✓ 精选海滨度假村\n"
                "✓ 本地文化体验\n"
                "✓ 灵活定制行程"
            )
        return "为您精心打造独特的旅行体验"

    def _craft_emotional_appeal(self, destination: str) -> str:
        """Craft emotional appeal"""
        if destination == "saipan":
            return (
                "梦想假期不再遥远。想象碧波荡漾的马里亚纳，与家人在白沙滩上漫步，"
                "享受太平洋的温暖拥抱。我们的直飞班次让您轻松抵达，让休闲从登机那刻开始。"
            )
        elif destination == "phu_quoc":
            return (
                "厌倦了人挤人的热门景点？珍珠岛等待您的探索。在鲜有游客的海滩放松，"
                "品尝地道美食，发现真实的东南亚灵魂。"
            )
        return "开启一段改变生活的旅程"

    def _generate_cta(self, destination: str) -> str:
        """Generate call-to-action"""
        if destination == "saipan":
            return "预订您的马里亚纳梦想之旅 →"
        elif destination == "phu_quoc":
            return "发现珍珠岛的秘密 →"
        return "立即探索 →"

    def _generate_key_messages(self, destination: str) -> List[str]:
        """Generate key marketing messages"""
        if destination == "saipan":
            return [
                "独家HX直飞航班保证",
                "一价全包，无隐形消费",
                "五星级海滨酒店体验",
                "适合全家的安心之选",
                "专业中文导游与客服"
            ]
        elif destination == "phu_quoc":
            return [
                "新兴热门度假胜地",
                "物超所值的假期选择",
                "原生态海滩体验",
                "灵活自由的行程安排",
                "真实的越南文化沉浸"
            ]
        return ["Unique Experience", "Best Value", "Expert Service", "Memorable Journey"]

    def _generate_social_hooks(self, destination: str) -> List[str]:
        """Generate social media hooks"""
        if destination == "saipan":
            return [
                "💎 4999元就能体验太平洋奢华？点赞看详情 #SaipanDreams",
                "✈️ 直飞班次HX072让假期从天空开始 #LuxuryTravel",
                "🏝️ 晒出您的马里亚纳时刻，赢取下次免费升级 #SaipanEscape",
                "👨‍👩‍👧‍👦 全家出游，我们负责所有细节 #FamilyVacation"
            ]
        elif destination == "phu_quoc":
            return [
                "🌴 发现被低估的东南亚宝石 #PhuQuocSecrets",
                "💰 比预期便宜50%的海滩度假 #ValueTravel",
                "📸 这些景色值得一生铭记 #PhuQuoc",
                "🌊 拒绝拥挤，拥抱宁静的海滩 #BeachEscape"
            ]
        return ["🌍 Explore", "✨ Discover", "🎯 Experience"]

    def _generate_email_subjects(self, destination: str) -> List[str]:
        """Generate email subject line variants"""
        if destination == "saipan":
            return [
                "4999元起：独家HX直飞 + 五星酒店，您的马里亚纳梦想",
                "限量：这个价格的直飞塞班岛班次要没了",
                "家人已打包行李，只等您确认出发日期 ✈️",
                "VIP独享：塞班岛春季预售现已开启"
            ]
        elif destination == "phu_quoc":
            return [
                "意外发现：珍珠岛海滩度假竟然这么便宜？",
                "珍珠岛不再是秘密，赶快预订位置",
                "避开人海，发现真正的越南度假天堂",
                "闺蜜团、家庭游都在选的度假地"
            ]
        return [
            "限时优惠：您的完美假期等待中",
            "新目的地上线，早鸟价享受特惠",
            "探索更多，节省更多"
        ]


class AgentTeam:
    """Orchestrates multi-agent collaboration for comprehensive strategy"""

    def __init__(self):
        self.strategist = MarketStrategist()
        self.persona_expert = PersonaExpert()
        self.copywriter = CopywritingMaster()

    def _get_destination(self, product_data: Dict[str, Any]) -> ProductDestination:
        """Determine product destination"""
        destination = product_data.get("destination", "").lower()
        if "saipan" in destination or "塞班" in destination:
            return ProductDestination.SAIPAN
        elif "phu_quoc" in destination or "富国" in destination or "phú quốc" in destination:
            return ProductDestination.PHU_QUOC
        elif "hong kong" in destination or "hk" in destination or "香港" in destination:
            return ProductDestination.HK_MACAU
        elif "macau" in destination or "澳门" in destination or "macao" in destination:
            return ProductDestination.HK_MACAU
        return ProductDestination.OTHER

    def _validate_saipan_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and enforce Saipan-specific business logic
        """
        destination = self._get_destination(product_data)
        
        if destination != ProductDestination.SAIPAN:
            return product_data

        # Lock Saipan business logic
        validated = product_data.copy()
        
        # Flight numbers MUST be HX072/HX073
        validated["flight_number"] = "HX072/HX073"
        
        # Price must follow the pattern
        validated["price"] = "4999元起包含往返机票和酒店"
        
        # Add Saipan-specific metadata
        validated["locked_fields"] = ["flight_number", "price"]
        validated["saipan_exclusive"] = True
        
        return validated

    async def run_collaborative_brain(self, product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Chain-of-Thought collaborative analysis
        Simulates expert group discussion to output structural marketing strategy
        """
        
        # Validate business logic (especially for Saipan)
        product_data = self._validate_saipan_product(product_data)
        
        # Step 1: Market Strategist Analysis
        strategist_analysis = await self.strategist.analyze(product_data)
        
        # Step 2: Persona Expert Analysis (builds on strategist insights)
        persona_analysis = await self.persona_expert.analyze(product_data)
        
        # Step 3: Copywriting Master (synthesizes all insights)
        copywriting_output = await self.copywriter.analyze(
            product_data,
            strategist_analysis,
            persona_analysis
        )
        
        # Step 4: Synthesize collaborative insights
        chain_of_thought = self._synthesize_cot(
            product_id,
            product_data,
            strategist_analysis,
            persona_analysis,
            copywriting_output
        )
        
        return {
            "product_id": product_id,
            "destination": product_data.get("destination"),
            "strategist_analysis": strategist_analysis,
            "persona_advice": persona_analysis,
            "copywriting_output": copywriting_output,
            "chain_of_thought": chain_of_thought,
            "locked_fields": product_data.get("locked_fields", []),
            "saipan_exclusive": product_data.get("saipan_exclusive", False)
        }

    def _synthesize_cot(self, product_id: int, product_data: Dict[str, Any],
                       strategist: Dict[str, Any], personas: Dict[str, Any],
                       copywriting: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize Chain-of-Thought reasoning across all agents
        """
        destination = self._get_destination(product_data)
        
        synthesis = {
            "reasoning_steps": [
                {
                    "step": 1,
                    "agent": "Market Strategist",
                    "focus": "Market positioning and competitive advantage",
                    "insight": strategist.get("positioning", "")
                },
                {
                    "step": 2,
                    "agent": "Persona Expert",
                    "focus": "Target audience identification and psychology",
                    "insight": f"Identified {len(personas.get('primary_personas', []))} primary personas"
                },
                {
                    "step": 3,
                    "agent": "Copywriting Master",
                    "focus": "Persuasive messaging and emotional engagement",
                    "insight": copywriting.get("primary_headline", "")
                }
            ],
            "strategic_recommendation": self._generate_strategic_recommendation(
                destination,
                strategist,
                personas,
                copywriting
            ),
            "implementation_priority": self._generate_implementation_priority(destination),
            "success_metrics": self._generate_success_metrics(destination),
            "risk_factors": self._identify_risk_factors(destination)
        }
        
        return synthesis

    def _generate_strategic_recommendation(self, destination: ProductDestination,
                                         strategist: Dict, personas: Dict, copywriting: Dict) -> str:
        """Generate strategic recommendation"""
        if destination == ProductDestination.SAIPAN:
            return (
                "Focus on premium positioning leveraging HX direct flights as unique selling point. "
                "Target affluent families and honeymooners with all-inclusive messaging. "
                "Emphasize exclusivity and convenience. Use social proof from VIP travelers. "
                "Maintain 4999元起 pricing to signal value despite premium positioning."
            )
        elif destination == ProductDestination.PHU_QUOC:
            return (
                "Position as emerging alternative to overcrowded Southeast Asian destinations. "
                "Target budget-conscious explorers and families seeking authentic experiences. "
                "Emphasize value for money and discovery narrative. "
                "Leverage UGC and influencer content for authenticity."
            )
        return "Develop value-based messaging highlighting unique experiences and competitive pricing."

    def _generate_implementation_priority(self, destination: ProductDestination) -> List[Dict[str, Any]]:
        """Generate implementation priorities"""
        if destination == ProductDestination.SAIPAN:
            return [
                {"priority": 1, "action": "Secure HX flight partnership exclusivity", "timeline": "Immediate"},
                {"priority": 2, "action": "Launch premium positioning campaign", "timeline": "Week 1-2"},
                {"priority": 3, "action": "Develop VIP customer testimonial series", "timeline": "Week 2-3"},
                {"priority": 4, "action": "Implement luxury hotel partnership program", "timeline": "Week 3-4"}
            ]
        return [
            {"priority": 1, "action": "Content creation and UGC collection", "timeline": "Week 1-2"},
            {"priority": 2, "action": "Influencer partnerships", "timeline": "Week 2-3"},
            {"priority": 3, "action": "Social media campaign launch", "timeline": "Week 3"}
        ]

    def _generate_success_metrics(self, destination: ProductDestination) -> Dict[str, Any]:
        """Generate success metrics"""
        if destination == ProductDestination.SAIPAN:
            return {
                "conversion_rate": "Target: 3-5% from marketing-qualified leads",
                "average_booking_value": "Target: 15,000元+ per customer",
                "customer_satisfaction": "Target: 4.8/5.0 rating",
                "repeat_booking_rate": "Target: 25%+ within 12 months",
                "social_sharing_rate": "Target: 40%+ of customers share on social media"
            }
        return {
            "conversion_rate": "Target: 2-4% from marketing-qualified leads",
            "customer_acquisition_cost": "Target: ROI 3:1 or better",
            "organic_reach": "Target: 50% of impressions from organic channels"
        }

    def _identify_risk_factors(self, destination: ProductDestination) -> List[str]:
        """Identify potential risk factors"""
        if destination == ProductDestination.SAIPAN:
            return [
                "Flight schedule disruptions affecting HX072/HX073",
                "US visa policy changes affecting accessibility",
                "Typhoon season impact on operations (July-October)",
                "Economic downturn reducing premium travel demand",
                "Competitive pricing pressure from other carriers"
            ]
        elif destination == ProductDestination.PHU_QUOC:
            return [
                "Infrastructure development uncertainties",
                "Seasonal weather unpredictability",
                "Visa complexity for non-Vietnamese travelers",
                "Language barriers affecting experience quality",
                "Currency fluctuation risks"
            ]
        return ["Economic factors", "Seasonal variations", "Competitive pressure"]


# Export for API usage
async def create_agent_team_analysis(product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Factory function to create agent team analysis
    """
    team = AgentTeam()
    return await team.run_collaborative_brain(product_id, product_data)
