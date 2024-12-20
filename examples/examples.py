# examples/examples.py

class MermaidExamples:
    @staticmethod
    def get_software_architecture():
        return """
        graph TD
            Client[Web Client] --> API{API Gateway}
            API --> Auth[Authentication]
            API --> Cache[(Redis Cache)]
            API --> DB[(Database)]
            Auth --> DB
            API --> Queue[Message Queue]
            Queue --> Workers[Background Workers]
            Workers --> DB
        """
    
    @staticmethod
    def get_business_process():
        return """
        graph LR
            Lead[New Lead] --> Qualify{Qualification}
            Qualify -->|Qualified| Meeting[Schedule Meeting]
            Qualify -->|Not Ready| Nurture[Nurture Campaign]
            Meeting --> Demo[Product Demo]
            Demo --> Proposal[Send Proposal]
            Proposal --> Close{Decision}
            Close -->|Won| Onboard[Customer Onboarding]
            Close -->|Lost| Feedback[Get Feedback]
            Nurture --> Qualify
        """
    
    @staticmethod
    def get_system_state():
        return """
        graph TD
            Idle[System Idle] --> Active{User Activity}
            Active -->|Data Request| Processing[Processing]
            Active -->|Timeout| Sleep[Sleep Mode]
            Processing --> Cache[(Check Cache)]
            Cache -->|Hit| Return[Return Data]
            Cache -->|Miss| Fetch[Fetch Data]
            Fetch --> Store[Update Cache]
            Store --> Return
            Sleep --> Idle
            Return --> Idle
        """

    @staticmethod
    def get_indian_economy():
        return """
        graph TD
            India[Indian Economy] --> Pre91[Pre-1991 Era]
            India --> Post91[Post-1991 Era]
            
            Pre91 --> SovietModel[Soviet Model]
            SovietModel -->|Characterized by| LicenceRaj{Licence Raj}
            
            Post91 -->|Triggered by| Crisis[Balance of Payment Crisis]
            Post91 -->|Led to| Liberal[Economic Liberalization]
            
            India --> KeySectors{Key State-Controlled Sectors}
            
            KeySectors -->|Complete Control| Transport[Railways & Highways]
            KeySectors -->|Major Control| Banking[Banking & Insurance]
            KeySectors -->|Strategic| Defense[Defense & Space]
            KeySectors -->|Infrastructure| Energy[Energy & Utilities]
            KeySectors -->|Digital| Tech[Telecom & Broadband]
            
            Liberal -->|Result| Mixed[Mixed Economy]
            Mixed -->|Features| Public[Strong Public Sector]
            Mixed -->|Ranking| GDP[5th Largest by GDP]
        """