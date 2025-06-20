import {
  useChat, // Added for sending text messages
  useVoiceAssistant,
  BarVisualizer,
  VoiceAssistantControlBar,
  useTrackTranscription,
  useLocalParticipant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useEffect, useState, useCallback } from "react"; // Added useCallback
import "./SimpleVoiceAssistant.css";

const Message = ({ type, text }) => {
  return <div className="message">
    <strong className={`message-${type}`}>
      {type === "agent" ? "Agent: " : "You: "}
    </strong>
    <span className="message-text">{text}</span>
  </div>;
};

const SimpleVoiceAssistant = () => {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const localParticipant = useLocalParticipant();
  const { segments: userTranscriptions } = useTrackTranscription({
    publication: localParticipant.microphoneTrack,
    source: Track.Source.Microphone,
    participant: localParticipant.localParticipant,
  });

  const [messages, setMessages] = useState([]);

  // State for Adherent Details, Contracts, and Claims
  const [adherentDetails, setAdherentDetails] = useState(null);
  const [contracts, setContracts] = useState([]);
  const [claims, setClaims] = useState([]);

  // State for Adherent Lookup form inputs
  const [lookupEmail, setLookupEmail] = useState("");
  const [lookupPhone, setLookupPhone] = useState("");
  const [lookupName, setLookupName] = useState(""); // Assuming 'Name' could be last name or full name
  const [lookupFirstName, setLookupFirstName] = useState(""); // Added for first name

  // State for Create Claim form inputs
  const [claimContractId, setClaimContractId] = useState("");
  const [claimType, setClaimType] = useState("");
  const [claimDescription, setClaimDescription] = useState("");
  const [claimIncidentDate, setClaimIncidentDate] = useState("");

  // System message state for feedback (e.g., claim creation status)
  const [systemMessage, setSystemMessage] = useState("");

  // Loading/error states (optional for now, can be added later if needed)
  // const [isLoadingAdherent, setIsLoadingAdherent] = useState(false);
  // const [adherentError, setAdherentError] = useState(null);

  // Access the send function from useChat for sending text messages to the agent
  const { send } = useChat();

  // Helper function to parse adherent data from agent message
  // This is a simplified parser and might need to be adjusted based on actual agent response format
  const parseAdherentData = (text) => {
    const lines = text.split('\n');
    const details = {};
    let foundDetails = false;

    // Example parsing logic, very basic
    // Assumes agent might send something like:
    // "Adherent Details Found:
    // ID: 123
    // Name: John Doe
    // Email: john@example.com
    // Phone: 555-1234"
    // Or JSON stringified: {"id": "123", "firstName": "John", "lastName": "Doe", ...}

    // Try parsing as JSON first
    try {
      const jsonData = JSON.parse(text);
      if (jsonData && jsonData.id && (jsonData.firstName || jsonData.lastName || jsonData.name)) {
        // Simple check for common adherent fields
        // The backend should ideally send a structured JSON for this
        setAdherentDetails({
            id: jsonData.id,
            firstName: jsonData.firstName || '',
            lastName: jsonData.lastName || jsonData.name || '', // if 'name' is full name
            email: jsonData.email || '',
            phone: jsonData.phone || '',
            //... any other fields
        });
        setContracts(jsonData.contracts || []); // Expecting contracts array
        setClaims(jsonData.claims || []);       // Expecting claims array
        return true;
      }
    } catch (e) {
      // Not JSON, try regex or line-by-line parsing
    }

    // Fallback to line-by-line parsing (less reliable)
    lines.forEach(line => {
      if (line.startsWith("ID:")) details.id = line.substring(3).trim();
      else if (line.startsWith("Name:")) {
        const nameParts = line.substring(5).trim().split(" ");
        details.firstName = nameParts[0];
        details.lastName = nameParts.slice(1).join(" ");
        foundDetails = true; // Mark that we found something that looks like a name
      } else if (line.startsWith("Email:")) details.email = line.substring(6).trim();
      else if (line.startsWith("Phone:")) details.phone = line.substring(6).trim();
    });

    // Condition to ensure we have at least an ID and some form of name before setting adherent details
    if (details.id && (details.firstName || details.lastName)) {
      setAdherentDetails(details);
      setContracts([]); // Clear previous contracts
      setClaims([]);    // Clear previous claims
      return true; // Indicates adherent data was likely parsed
    }
    return false; // No adherent data parsed by this method
  };

  // Parsing function for contracts
  const parseContractsData = (text) => {
    // Example: "Here are the contracts for Adherent ID 123:
    //   - Contract ID: C1, Number: N1, Status: Active, Type: Health
    //   - Contract ID: C2, Number: N2, Status: Inactive, Type: Dental"
    if (!text.toLowerCase().includes("here are the contracts")) return false;

    const lines = text.split('\n');
    const parsedContracts = [];
    lines.forEach(line => {
      if (line.trim().startsWith("- Contract ID:")) {
        const idMatch = line.match(/Contract ID: ([^,]+)/);
        const numMatch = line.match(/Number: ([^,]+)/);
        const statMatch = line.match(/Status: ([^,]+)/);
        const typeMatch = line.match(/Type: (.+)/);
        if (idMatch && numMatch && statMatch && typeMatch) {
          parsedContracts.push({
            id: idMatch[1].trim(),
            number: numMatch[1].trim(),
            status: statMatch[1].trim(),
            type: typeMatch[1].trim(),
          });
        }
      }
    });
    if (parsedContracts.length > 0) {
      setContracts(parsedContracts);
      return true;
    }
    return false;
  };

  // Parsing function for claims
  const parseClaimsData = (text) => {
    // Example: "Here are the claims for Adherent ID 123:
    //   - Claim ID: CLM1, Type: Doctor Visit, Status: Approved, Date: 2023-01-15
    //   - Claim ID: CLM2, Type: Prescription, Status: Pending, Date: 2023-02-01"
    if (!text.toLowerCase().includes("here are the claims")) return false;

    const lines = text.split('\n');
    const parsedClaims = [];
    lines.forEach(line => {
      if (line.trim().startsWith("- Claim ID:")) {
        const idMatch = line.match(/Claim ID: ([^,]+)/);
        const typeMatch = line.match(/Type: ([^,]+)/);
        const statusMatch = line.match(/Status: ([^,]+)/);
        const dateMatch = line.match(/Date: (.+)/);
        if (idMatch && typeMatch && statusMatch && dateMatch) {
          parsedClaims.push({
            id: idMatch[1].trim(),
            type: typeMatch[1].trim(),
            status: statusMatch[1].trim(),
            date: dateMatch[1].trim(),
          });
        }
      }
    });
    if (parsedClaims.length > 0) {
      setClaims(parsedClaims);
      return true;
    }
    return false;
  };

  // Function to parse claim creation confirmation
  const parseClaimCreationResponse = (text) => {
    // Example: "Claim created successfully. ID: CLM12345"
    // Or: "Error creating claim: Invalid contract ID"
    if (text.toLowerCase().includes("claim created successfully")) {
      setSystemMessage(text);
      // Potentially clear claim form or update claims list if needed
      setClaimContractId("");
      setClaimType("");
      setClaimDescription("");
      setClaimIncidentDate("");
      // Optionally, trigger a refresh of claims list:
      // if (adherentDetails?.id && send) send("list_adherent_claims");
      return true;
    } else if (text.toLowerCase().includes("error creating claim")) {
      setSystemMessage(text);
      return true;
    }
    return false;
  };


  useEffect(() => {
    const allMessages = [
      ...(agentTranscriptions?.map((t) => ({ ...t, type: "agent" })) ?? []),
      ...(userTranscriptions?.map((t) => ({ ...t, type: "user" })) ?? []),
    ].sort((a, b) => a.firstReceivedTime - b.firstReceivedTime);
    setMessages(allMessages);

    // Process agent transcriptions
    agentTranscriptions?.forEach(transcription => {
      if (transcription.text) {
        setSystemMessage(""); // Clear previous system message
        if (parseAdherentData(transcription.text)) {
          console.log("Adherent data updated from agent message.");
        } else if (parseContractsData(transcription.text)) {
          console.log("Contracts data updated from agent message.");
        } else if (parseClaimsData(transcription.text)) {
          console.log("Claims data updated from agent message.");
        } else if (parseClaimCreationResponse(transcription.text)) {
          console.log("Claim creation response processed.");
        }
      }
    });
  }, [agentTranscriptions, userTranscriptions]);


  const handleLookupSubmit = useCallback(async (event) => {
    event.preventDefault();
    if (!send) {
      console.error("Send function is not available from useChat.");
      return;
    }

    let message = "";
    if (lookupEmail) {
      message = `lookup_adherent_by_email ${lookupEmail}`;
    } else if (lookupPhone) {
      message = `lookup_adherent_by_phone ${lookupPhone}`;
    } else if (lookupFirstName && lookupName) {
      message = `lookup_adherent_by_name ${lookupFirstName} ${lookupName}`;
    } else if (lookupName) { // Assuming lookupName can be for last name if first name is empty
      message = `lookup_adherent_by_last_name ${lookupName}`;
    } else {
      console.log("No lookup criteria provided.");
      // Optionally, show a message to the user
      return;
    }

    if (message) {
      console.log("Sending message to agent:", message);
      await send(message);
      // Clear form fields after sending
      setLookupEmail("");
      setLookupPhone("");
      setLookupName("");
      setLookupFirstName("");
      // Clear previous details when new lookup is initiated
      setAdherentDetails(null);
      setContracts([]);
      setClaims([]);
      setSystemMessage(""); // Clear system message on new lookup
    }
  }, [send, lookupEmail, lookupPhone, lookupName, lookupFirstName]);

  const handleShowContracts = useCallback(async () => {
    if (!adherentDetails?.id) {
      setSystemMessage("No adherent selected. Please lookup an adherent first.");
      return;
    }
    if (!send) {
      console.error("Send function is not available.");
      setSystemMessage("Error: Cannot connect to agent.");
      return;
    }
    const message = `list_adherent_contracts`; // Assuming adherent_id is implicit in agent's context
    console.log("Requesting contracts:", message);
    await send(message);
    setSystemMessage("Requesting contracts...");
  }, [send, adherentDetails]);

  const handleShowClaims = useCallback(async () => {
    if (!adherentDetails?.id) {
      setSystemMessage("No adherent selected. Please lookup an adherent first.");
      return;
    }
    if (!send) {
      console.error("Send function is not available.");
      setSystemMessage("Error: Cannot connect to agent.");
      return;
    }
    const message = `list_adherent_claims`; // Assuming adherent_id is implicit in agent's context
    console.log("Requesting claims:", message);
    await send(message);
    setSystemMessage("Requesting claims...");
  }, [send, adherentDetails]);

  const handleClaimSubmit = useCallback(async (event) => {
    event.preventDefault();
    if (!send) {
      console.error("Send function is not available.");
      setSystemMessage("Error: Cannot connect to agent to create claim.");
      return;
    }
    if (!claimContractId || !claimType || !claimDescription || !claimIncidentDate) {
      setSystemMessage("Please fill all fields for the new claim.");
      return;
    }

    // Construct the message for creating a claim
    // Adjust syntax based on backend agent's requirements for tool use
    const message = `create_claim --contract_id ${claimContractId} --type "${claimType}" --description "${claimDescription}" --incident_date ${claimIncidentDate}`;

    console.log("Submitting new claim:", message);
    await send(message);
    setSystemMessage("Submitting new claim...");
    // Clearing fields is now handled by parseClaimCreationResponse on success
  }, [send, claimContractId, claimType, claimDescription, claimIncidentDate]);

  return (
    <div className="voice-assistant-container">
      {systemMessage && <div className="system-message">{systemMessage}</div>}
      <div className="visualizer-container">
        <BarVisualizer state={state} barCount={7} trackRef={audioTrack} />
      </div>
      <div className="control-section">
        <VoiceAssistantControlBar />
        <div className="conversation">
          {messages.map((msg, index) => (
            <Message key={msg.id || index} type={msg.type} text={msg.text} />
          ))}
        </div>
      </div>
      <div className="info-sections">
        <section className="adherent-details-section">
          <h2>Adherent Details</h2>
          {adherentDetails ? (
            <>
              <p>ID: {adherentDetails.id}</p>
              <p>Name: {adherentDetails.firstName} {adherentDetails.lastName}</p>
              <p>Email: {adherentDetails.email}</p>
              <p>Phone: {adherentDetails.phone}</p>
              {/* Add more fields as necessary */}
              <div className="adherent-actions">
                <button onClick={handleShowContracts} disabled={!adherentDetails?.id}>Show Contracts</button>
                <button onClick={handleShowClaims} disabled={!adherentDetails?.id}>Show Claims</button>
              </div>
            </>
          ) : (
            <p>No adherent details loaded.</p>
          )}
        </section>
        <section className="contracts-section">
          <h2>Contracts</h2>
          {contracts.length > 0 ? (
            <ul>
              {contracts.map(contract => (
                <li key={contract.id}>
                  ID: {contract.id}, Number: {contract.number}, Status: {contract.status}, Type: {contract.type}
                </li>
              ))}
            </ul>
          ) : (
            <p>No contracts found or loaded for the current adherent.</p>
          )}
        </section>
        <section className="claims-section">
          <h2>Claims</h2>
          {claims.length > 0 ? (
            <ul>
              {claims.map(claim => (
                <li key={claim.id}>
                  ID: {claim.id}, Type: {claim.type}, Status: {claim.status}, Date: {claim.date}
                </li>
              ))}
            </ul>
          ) : (
            <p>No claims found or loaded for the current adherent.</p>
          )}
        </section>
        <section className="new-claim-section">
          <h2>Create New Claim</h2>
          <form onSubmit={handleClaimSubmit}>
            <div>
              <label htmlFor="claimContractId">Contract ID:</label>
              <input type="text" id="claimContractId" name="claimContractId" value={claimContractId} onChange={e => setClaimContractId(e.target.value)} />
            </div>
            <div>
              <label htmlFor="claimType">Claim Type:</label>
              <input type="text" id="claimType" name="claimType" value={claimType} onChange={e => setClaimType(e.target.value)} />
            </div>
            <div>
              <label htmlFor="claimDescription">Description:</label>
              <textarea id="claimDescription" name="claimDescription" value={claimDescription} onChange={e => setClaimDescription(e.target.value)}></textarea>
            </div>
            <div>
              <label htmlFor="claimIncidentDate">Incident Date:</label>
              <input type="date" id="claimIncidentDate" name="claimIncidentDate" value={claimIncidentDate} onChange={e => setClaimIncidentDate(e.target.value)} />
            </div>
            <button type="submit">Submit Claim</button>
          </form>
        </section>
        <section className="adherent-lookup-section">
          <h2>Adherent Lookup</h2>
          <form onSubmit={handleLookupSubmit}>
            <div>
              <label htmlFor="lookup_firstName">First Name:</label>
              <input type="text" id="lookup_firstName" name="lookup_firstName" value={lookupFirstName} onChange={e => setLookupFirstName(e.target.value)}/>
            </div>
            <div>
              <label htmlFor="lookup_name">Last Name:</label>
              <input type="text" id="lookup_name" name="lookup_name" value={lookupName} onChange={e => setLookupName(e.target.value)}/>
            </div>
            <div>
              <label htmlFor="lookup_email">Email:</label>
              <input type="email" id="lookup_email" name="lookup_email" value={lookupEmail} onChange={e => setLookupEmail(e.target.value)}/>
            </div>
            <div>
              <label htmlFor="lookup_phone">Phone:</label>
              <input type="tel" id="lookup_phone" name="lookup_phone" value={lookupPhone} onChange={e => setLookupPhone(e.target.value)}/>
            </div>
            <button type="submit">Search Adherent</button>
          </form>
        </section>
      </div>
    </div>
  );
};

export default SimpleVoiceAssistant;
