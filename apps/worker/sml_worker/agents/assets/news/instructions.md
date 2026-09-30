Validation Instructions: 

Task Description
Objective: Verify the authenticity and context of multimedia content, which may be in a language other than English, and provide both a detailed report for fact-checkers and a concise summary for general readers. The languages of the content might not be in English.

Input: Each case/task will provide (in a zip file):

Multimedia Content: Image(s) or video(s)

Associated Context: Captions, descriptions, social media posts, news articles, metadata (if available)

Additional Clues: Possible sources, claims, or fact-checker notes (if relevant)

Output: A verification report (as a text file) in English. The report should include the following key information:

Summary of Key Points: Provide a concise overview of the content, including relevant details. Clearly highlight any uncertainties and underline what is not yet known.

Content Category: Assign relevant tags based on platforms, people, brands, or specific topics.

Forensic Analysis Results:

Authenticity: Determine if the content is synthetic, modified, or recaptured.

Tools & Methods Used: Specify the verification tools and techniques applied.

Synthetic Type (if applicable): Identify whether it was generated using GANs, Stable Diffusion, or other AI models.

Other Artifacts: Note any detected anomalies or manipulations.

Verified Evidence: State what can be confirmed about the video/photo based on available evidence.

Source Details: Where the content comes from (URLs, original posts, etc.)

Where? (Location)

When? (Time)

Who? (People, organizations, entities involved)

Why? (Possible motivations or intent)

Other Evidence & Findings: Any additional relevant information, supporting materials, or external sources

Note: For each evidence finding, specify the failure type if verification fails: Indeterminate (insufficient or ambiguous data), Inconclusive (attempted but no definitive result), or Not Feasible (limited expertise or tools).


PDF Document

Freestyle Text under Report/* which is a latex format for ACM that should provides a detailed explanation of the approach and methodology used to solve the challenge.

There are no strict formatting guidelines; however, clarity and structure are encouraged.

Technical Paper 

A team of agent should work on ICMR 2026 submission based on results, a technical paper (4 pages + plus additional pages for the list of references) must be created publication ready.

The paper must be formatted according to the ACM proceedings style I have already put the format. 



All challenge submissions will be peer-reviewed to ensure maximum quality and accepted papers will be included in the conference proceedings so please do the work professionally generate professional looking figures. 


Reports must be in Markdown (.md) format. The file name of the report is report.md

Folder report contains supporting media files for the MD file.

The submission file for each case is the ZIP file that contains above files and folders with this name: teamname_caseID.zip

You can find the sample here.  

Report Structure

# Case Summary  

- Brief overview of the verification findings.  



# Content Classification  

- **Tags:** Assign relevant tags based on platforms, people, brands, or specific topics (e.g., TikTok, Trump, Coca-Cola, Ukraine War, or AI-generated).



# Verified Evidence  

- **Source Details:** Identify where the content originates (URLs, original posts, metadata).  

- **Where? (Location):** Determine the correct geographical context.  

- **When? (Time):** Establish the accurate timeframe.  

- **Who? (Entities Involved):** Identify key individuals or groups.  

- **Why? (Motivation or Intent):** Provide a reasoned explanation of possible intent.  



# Forensic Analysis  

- **Authenticity Assessment:** Determine if the content is synthetic, modified, or recaptured.  

- **Verification Tools & Methods:** Clearly document the tools and techniques used.  

- **Synthetic Type (if applicable):** Identify AI-generated content (e.g., GANs, Stable Diffusion).  

- **Other Artifacts:** Note any detected anomalies or manipulations.  



# Other Evidence & Findings  

- **Supporting Sources:** Use additional fact-checks, reports, or metadata to back claims.  

- **Cross-Checking Information:** Ensure verification through multiple independent sources.  

- **Other Info:** Unclassified supporting evidence and analysis.        