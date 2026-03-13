"""
Neo4j Sync Service for PDL Persons

Creates person nodes and relationships for:
- Career path analysis
- Company networks
- Skill co-occurrence  
- Professional recommendations
- Influence mapping

Graph Structure:
- (Person)-[:WORKS_AT]->(Company)
- (Person)-[:HAS_SKILL]->(Skill)
- (Person)-[:LOCATED_IN]->(Location)
- (Person)-[:WORKED_AT]->(Company) [historical from work_history]
"""
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable

from src.core.logging import get_logger, LogCategory, bind_context
from src.core.config import get_settings
from src.models.connector import PDLPerson

logger = get_logger(__name__, LogCategory.BUSINESS)


class Neo4jSyncService:
    """Service for syncing PDL persons to Neo4j graph database."""
    
    def __init__(self, driver: Optional[Driver] = None):
        """
        Initialize Neo4j sync service.
        
        Args:
            driver: Optional Neo4j driver (for testing)
        """
        settings = get_settings()
        
        if driver:
            self.driver = driver
        else:
            # Connect to Neo4j
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
        
        logger.info("neo4j_sync_initialized", uri=settings.neo4j_uri if not driver else "test_driver")
        
        # Create indexes for performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Create indexes on frequently queried properties."""
        try:
            with self.driver.session() as session:
                # Person indexes
                session.run("CREATE INDEX person_pdl_id IF NOT EXISTS FOR (p:Person) ON (p.pdl_id)")
                session.run("CREATE INDEX person_customer IF NOT EXISTS FOR (p:Person) ON (p.customer_id)")
                session.run("CREATE INDEX person_email IF NOT EXISTS FOR (p:Person) ON (p.email)")
                
                # Company indexes
                session.run("CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)")
                
                # Skill indexes
                session.run("CREATE INDEX skill_name IF NOT EXISTS FOR (s:Skill) ON (s.name)")
                
                # Location indexes
                session.run("CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name)")
                
                logger.info("neo4j_indexes_created")
                
        except Exception as e:
            logger.warning(f"Could not create Neo4j indexes: {e}")
    
    def sync_person(self, person: PDLPerson) -> bool:
        """
        Sync a person to Neo4j graph.
        
        Creates/updates:
        - Person node
        - Company node + WORKS_AT relationship
        - Skill nodes + HAS_SKILL relationships
        - Location node + LOCATED_IN relationship
        
        Args:
            person: PDLPerson model instance
            
        Returns:
            True if successful
        """
        try:
            bind_context(
                operation="sync_person_neo4j",
                pdl_id=person.pdl_id,
                customer_id=person.customer_id
            )
            
            with self.driver.session() as session:
                # 1. Create/Update Person node
                self._upsert_person_node(session, person)
                
                # 2. Create Company relationship (current job)
                if person.job_company_name:
                    self._create_company_relationship(session, person)
                
                # 3. Create Skill relationships
                if person.skills:
                    self._create_skill_relationships(session, person)
                
                # 4. Create Location relationship
                if person.location_country:
                    self._create_location_relationship(session, person)
                
                # 5. Create historical work relationships (if available)
                if person.work_history:
                    self._create_work_history_relationships(session, person)
            
            logger.info(
                "person_synced_neo4j",
                pdl_id=person.pdl_id,
                customer_id=person.customer_id
            )
            
            return True
            
        except ServiceUnavailable as e:
            logger.error("neo4j_unavailable", error=str(e))
            return False
        except Exception as e:
            logger.error(
                "person_sync_neo4j_failed",
                pdl_id=person.pdl_id if person else None,
                error=str(e),
                exc_info=True
            )
            return False
    
    def _upsert_person_node(self, session, person: PDLPerson):
        """Create or update Person node."""
        query = """
        MERGE (p:Person {pdl_id: $pdl_id, customer_id: $customer_id})
        SET p.name = $name,
            p.first_name = $first_name,
            p.last_name = $last_name,
            p.email = $email,
            p.linkedin_url = $linkedin_url,
            p.current_title = $current_title,
            p.current_company = $current_company,
            p.pdl_likelihood = $pdl_likelihood,
            p.sync_count = $sync_count,
            p.updated_at = datetime($updated_at)
        """
        
        session.run(
            query,
            pdl_id=person.pdl_id,
            customer_id=person.customer_id,
            name=person.full_name,
            first_name=person.first_name,
            last_name=person.last_name,
            email=person.primary_email,
            linkedin_url=person.linkedin_url,
            current_title=person.job_title,
            current_company=person.job_company_name,
            pdl_likelihood=person.pdl_likelihood,
            sync_count=person.sync_count,
            updated_at=person.updated_at.isoformat() if person.updated_at else None
        )
    
    def _create_company_relationship(self, session, person: PDLPerson):
        """Create Person->Company WORKS_AT relationship."""
        query = """
        MATCH (p:Person {pdl_id: $pdl_id, customer_id: $customer_id})
        MERGE (c:Company {name: $company_name})
        ON CREATE SET c.created_at = datetime()
        MERGE (p)-[r:WORKS_AT]->(c)
        SET r.title = $title,
            r.title_role = $title_role,
            r.start_date = $start_date,
            r.company_size = $company_size,
            r.company_industry = $company_industry,
            r.current = true,
            r.updated_at = datetime()
        """
        
        session.run(
            query,
            pdl_id=person.pdl_id,
            customer_id=person.customer_id,
            company_name=person.job_company_name,
            title=person.job_title,
            title_role=person.job_title_role,
            start_date=person.job_start_date.isoformat() if person.job_start_date else None,
            company_size=person.job_company_size,
            company_industry=person.job_company_industry
        )
    
    def _create_skill_relationships(self, session, person: PDLPerson):
        """Create Person->Skill HAS_SKILL relationships."""
        # Extract skill names
        skills = []
        if isinstance(person.skills, list):
            for skill in person.skills:
                if isinstance(skill, dict):
                    skill_name = skill.get("name")
                    if skill_name:
                        skills.append(skill_name)
                elif isinstance(skill, str):
                    skills.append(skill)
        
        if not skills:
            return
        
        # Create relationships (batch)
        query = """
        UNWIND $skills as skill_name
        MATCH (p:Person {pdl_id: $pdl_id, customer_id: $customer_id})
        MERGE (s:Skill {name: skill_name})
        MERGE (p)-[r:HAS_SKILL]->(s)
        SET r.updated_at = datetime()
        """
        
        session.run(
            query,
            pdl_id=person.pdl_id,
            customer_id=person.customer_id,
            skills=skills
        )
    
    def _create_location_relationship(self, session, person: PDLPerson):
        """Create Person->Location LOCATED_IN relationship."""
        query = """
        MATCH (p:Person {pdl_id: $pdl_id, customer_id: $customer_id})
        MERGE (l:Location {
            country: $country,
            region: $region,
            locality: $locality
        })
        ON CREATE SET l.name = $location_name
        MERGE (p)-[r:LOCATED_IN]->(l)
        SET r.updated_at = datetime()
        """
        
        session.run(
            query,
            pdl_id=person.pdl_id,
            customer_id=person.customer_id,
            country=person.location_country,
            region=person.location_region,
            locality=person.location_locality,
            location_name=person.location_name
        )
    
    def _create_work_history_relationships(self, session, person: PDLPerson):
        """Create historical WORKED_AT relationships from work history."""
        if not person.work_history or not isinstance(person.work_history, list):
            return
        
        for job in person.work_history:
            if not isinstance(job, dict):
                continue
            
            company_name = job.get("company_name") or job.get("company", {}).get("name")
            if not company_name:
                continue
            
            query = """
            MATCH (p:Person {pdl_id: $pdl_id, customer_id: $customer_id})
            MERGE (c:Company {name: $company_name})
            ON CREATE SET c.created_at = datetime()
            MERGE (p)-[r:WORKED_AT]->(c)
            SET r.title = $title,
                r.start_date = $start_date,
                r.end_date = $end_date,
                r.current = false,
                r.updated_at = datetime()
            """
            
            session.run(
                query,
                pdl_id=person.pdl_id,
                customer_id=person.customer_id,
                company_name=company_name,
                title=job.get("title"),
                start_date=job.get("start_date"),
                end_date=job.get("end_date")
            )
    
    def delete_person(self, pdl_id: str, customer_id: str) -> bool:
        """
        Delete person node and all relationships.
        
        Args:
            pdl_id: PDL person ID
            customer_id: Customer ID
            
        Returns:
            True if successful
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (p:Person {pdl_id: $pdl_id, customer_id: $customer_id})
                DETACH DELETE p
                """
                
                session.run(query, pdl_id=pdl_id, customer_id=customer_id)
            
            logger.info("person_deleted_neo4j", pdl_id=pdl_id)
            return True
            
        except Exception as e:
            logger.error("person_deletion_neo4j_failed", pdl_id=pdl_id, error=str(e))
            return False
    
    def find_career_transitions(
        self,
        customer_id: str,
        from_company: str,
        to_company: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find people who transitioned from one company to another.
        
        Useful for understanding career paths and talent pipelines.
        
        Args:
            customer_id: Customer ID
            from_company: Source company name
            to_company: Destination company name
            limit: Max results
            
        Returns:
            List of person nodes with career transition info
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (start:Company {name: $from_company})<-[:WORKED_AT]-(p:Person {customer_id: $customer_id}),
                      (p)-[:WORKS_AT]->(end:Company {name: $to_company})
                RETURN p.pdl_id as pdl_id,
                       p.name as name,
                       p.email as email,
                       p.current_title as current_title,
                       p.linkedin_url as linkedin_url
                LIMIT $limit
                """
                
                result = session.run(
                    query,
                    customer_id=customer_id,
                    from_company=from_company,
                    to_company=to_company,
                    limit=limit
                )
                
                persons = [dict(record) for record in result]
                
                logger.info(
                    "career_transitions_found",
                    from_company=from_company,
                    to_company=to_company,
                    count=len(persons)
                )
                
                return persons
                
        except Exception as e:
            logger.error("career_transition_query_failed", error=str(e), exc_info=True)
            return []
    
    def find_people_with_skills(
        self,
        customer_id: str,
        skills: List[str],
        require_all: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find people with specific skill combinations.
        
        Args:
            customer_id: Customer ID
            skills: List of skill names
            require_all: If True, person must have ALL skills. If False, ANY skill.
            limit: Max results
            
        Returns:
            List of person nodes
        """
        try:
            with self.driver.session() as session:
                if require_all:
                    # Must have ALL skills
                    query = """
                    MATCH (p:Person {customer_id: $customer_id})
                    WHERE ALL(skill IN $skills WHERE EXISTS {
                        MATCH (p)-[:HAS_SKILL]->(s:Skill {name: skill})
                    })
                    RETURN p.pdl_id as pdl_id,
                           p.name as name,
                           p.email as email,
                           p.current_title as current_title,
                           p.current_company as current_company
                    LIMIT $limit
                    """
                else:
                    # Must have ANY skill
                    query = """
                    MATCH (p:Person {customer_id: $customer_id})-[:HAS_SKILL]->(s:Skill)
                    WHERE s.name IN $skills
                    RETURN DISTINCT p.pdl_id as pdl_id,
                           p.name as name,
                           p.email as email,
                           p.current_title as current_title,
                           p.current_company as current_company
                    LIMIT $limit
                    """
                
                result = session.run(
                    query,
                    customer_id=customer_id,
                    skills=skills,
                    limit=limit
                )
                
                persons = [dict(record) for record in result]
                
                logger.info(
                    "skills_search_complete",
                    skills=skills,
                    require_all=require_all,
                    count=len(persons)
                )
                
                return persons
                
        except Exception as e:
            logger.error("skills_search_failed", error=str(e), exc_info=True)
            return []
    
    def get_company_network(
        self,
        customer_id: str,
        company_name: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get network of companies connected through people transitions.
        
        Finds companies that share employees (past or present).
        
        Args:
            customer_id: Customer ID
            company_name: Starting company
            depth: How many hops to traverse
            
        Returns:
            Dict with nodes and relationships
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH path = (start:Company {name: $company_name})<-[:WORKED_AT|WORKS_AT*1..$depth]-(p:Person {customer_id: $customer_id})-[:WORKED_AT|WORKS_AT*1..$depth]->(other:Company)
                WHERE start <> other
                WITH other, COUNT(DISTINCT p) as transition_count
                RETURN other.name as company_name,
                       transition_count
                ORDER BY transition_count DESC
                LIMIT 20
                """
                
                result = session.run(
                    query,
                    customer_id=customer_id,
                    company_name=company_name,
                    depth=depth
                )
                
                connections = [
                    {
                        "company": record["company_name"],
                        "transition_count": record["transition_count"]
                    }
                    for record in result
                ]
                
                logger.info(
                    "company_network_retrieved",
                    company=company_name,
                    connections=len(connections)
                )
                
                return {
                    "center_company": company_name,
                    "connections": connections
                }
                
        except Exception as e:
            logger.error("company_network_query_failed", error=str(e), exc_info=True)
            return {"center_company": company_name, "connections": []}
    
    def get_skill_cooccurrence(
        self,
        customer_id: str,
        skill: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Find skills that commonly appear together with a given skill.
        
        Useful for understanding skill clusters and job requirements.
        
        Args:
            customer_id: Customer ID
            skill: Skill name to analyze
            limit: Max results
            
        Returns:
            List of co-occurring skills with counts
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (p:Person {customer_id: $customer_id})-[:HAS_SKILL]->(s1:Skill {name: $skill}),
                      (p)-[:HAS_SKILL]->(s2:Skill)
                WHERE s1 <> s2
                WITH s2.name as cooccurring_skill, COUNT(p) as cooccurrence_count
                RETURN cooccurring_skill, cooccurrence_count
                ORDER BY cooccurrence_count DESC
                LIMIT $limit
                """
                
                result = session.run(
                    query,
                    customer_id=customer_id,
                    skill=skill,
                    limit=limit
                )
                
                skills = [
                    {
                        "skill": record["cooccurring_skill"],
                        "count": record["cooccurrence_count"]
                    }
                    for record in result
                ]
                
                logger.info(
                    "skill_cooccurrence_found",
                    skill=skill,
                    cooccurring_skills=len(skills)
                )
                
                return skills
                
        except Exception as e:
            logger.error("skill_cooccurrence_failed", error=str(e), exc_info=True)
            return []
    
    def close(self):
        """Close Neo4j driver."""
        if self.driver:
            self.driver.close()
            logger.info("neo4j_driver_closed")

