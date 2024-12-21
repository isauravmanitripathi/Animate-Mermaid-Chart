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

    @staticmethod
    def get_distributed_algorithm():
        return """
        graph TD
            Start((Input Array)) --> Split{Data Partitioning}
            
            Split -->|Chunk 1| P1[Partition 1]
            Split -->|Chunk 2| P2[Partition 2]
            Split -->|Chunk 3| P3[Partition 3]
            
            P1 --> V1{Validation 1}
            P2 --> V2{Validation 2}
            P3 --> V3{Validation 3}
            
            V1 -->|Valid| S1[QuickSort 1]
            V1 -->|Invalid| C1[Clean Data 1]
            V2 -->|Valid| S2[QuickSort 2]
            V2 -->|Invalid| C2[Clean Data 2]
            V3 -->|Valid| S3[QuickSort 3]
            V3 -->|Invalid| C3[Clean Data 3]
            
            C1 --> S1
            C2 --> S2
            C3 --> S3
            
            S1 --> M1{Merge Phase 1}
            S2 --> M1
            
            M1 --> SR1[Sorted Result 1]
            
            S3 --> M2{Merge Phase 2}
            SR1 --> M2
            
            M2 --> Final[Final Sorted Array]
            
            Final --> Analysis[Statistical Analysis]
            
            Analysis --> Mean[Calculate Mean]
            Analysis --> Median[Find Median]
            Analysis --> Mode[Compute Mode]
            Analysis --> StdDev[Standard Deviation]
            
            Mean --> Results((Statistical Results))
            Median --> Results
            Mode --> Results
            StdDev --> Results
            
            Results --> Cache[(Cache Results)]
            Results --> DB[(Store in Database)]
            
            Cache --> API{API Endpoint}
            DB --> API
            
            API -->|Success| Complete[Process Complete]
            API -->|Failure| Retry[Retry Logic]
            
            Retry --> Split
            
            subgraph Parallel Processing
            P1
            P2
            P3
            end
            
            subgraph Data Cleaning
            C1
            C2
            C3
            end
            
            subgraph Quick Sort
            S1
            S2
            S3
            end
            
            subgraph Statistical Computations
            Mean
            Median
            Mode
            StdDev
            end
            
            subgraph Storage Layer
            Cache
            DB
            end
        """