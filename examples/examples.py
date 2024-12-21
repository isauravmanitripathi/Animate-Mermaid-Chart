class MermaidExamples:
    @staticmethod
    def get_economy_lr():
        return """
        graph LR
            India[Indian Economy] --> Pre91[Pre-1991]
            India --> Post91[Post-1991]
            
            Pre91 --> Soviet[Soviet Model]
            Soviet --> License[License Raj]
            Soviet --> StateControl[State Control]
            
            Post91 --> Crisis[BOP Crisis]
            Post91 --> Liberal[Liberalization]
            Liberal --> Mixed[Mixed Economy]
            
            Mixed --> Public[Public Sector]
            Mixed --> Private[Private Sector]
            
            Public --> Core[Strategic Sectors]
            Core --> Rail[Railways]
            Core --> Highway[Highways]
            Core --> Bank[Banking]
            Core --> Defense[Defense]
            Core --> Digital[Digital Infrastructure]
            Core --> Energy[Energy]
        """
    
    @staticmethod
    def get_economy_td():
        return """
        graph TD
            Economy[Indian Economy] --> Historical[Historical Evolution]
            Economy --> Current[Current Structure]
            
            Historical --> Pre[Pre-1991 Era]
            Historical --> Post[Post-1991 Era]
            
            Pre --> Soviet[Soviet Model]
            Soviet --> Protect[Protectionist Policies]
            Soviet --> State[State Intervention]
            Soviet --> License[License Raj]
            
            Post --> Crisis[1991 Crisis]
            Post --> Liberal[Liberalization]
            Post --> Mixed[Mixed Economy]
            
            Current --> PSU[Public Sector]
            Current --> PVT[Private Sector]
            
            PSU --> Full[Complete Control]
            PSU --> Major[Major Control]
            PSU --> Strategic[Strategic Sectors]
            
            Full --> Transport[Railways & Highways]
            Major --> Banking[Banking & Insurance]
            Strategic --> Defense[Defense & Space]
            Strategic --> Digital[Digital & Telecom]
            Strategic --> Energy[Energy & Utilities]
        """