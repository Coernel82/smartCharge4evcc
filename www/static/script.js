// TODO: refresh page after deleting or editing a trip
// TODO: close modal after adding non recurring trip
// BUG: add recurring trip button not working

document.addEventListener('DOMContentLoaded', function() {
    // Function to populate brand dropdowns
    function populateBrandDropdown(targetId) {
        // Fetch EVCC_API_BASE_URL from settings.json
        fetch('load_settings')
            .then(response => response.json())
            .then(settings => {
                const EVCC_API_BASE_URL = settings.EVCC.EVCC_API_BASE_URL;

                // Fetch the vehicles from the EVCC API
                fetch(`${EVCC_API_BASE_URL}/api/state/`)
                    .then(response => response.json())
                    .then(data => {
                        const vehicles = data.result.vehicles;

                        // Check if vehicles data exists
                        if (!vehicles) {
                            console.error('Keine Fahrzeuge im API-Response gefunden.');
                            return;
                        }

                        // Filter vehicles to include only those with a 'capacity' field
                        const filteredBrands = Object.keys(vehicles).filter(brand => {
                            const vehicle = vehicles[brand];
                            return vehicle.hasOwnProperty('capacity') && typeof vehicle.capacity === 'number';
                        });

                        // Get the dropdown element by targetId
                        const brandSelect = document.getElementById(targetId);

                        // Ensure the dropdown element exists
                        if (!brandSelect) {
                            console.error(`Dropdown mit der ID "${targetId}" nicht gefunden.`);
                            return;
                        }

                        // Clear existing options
                        brandSelect.innerHTML = '';

                        // Optional: Add a default option
                        const defaultOption = document.createElement('option');
                        defaultOption.value = '';
                        defaultOption.textContent = 'Bitte eine Marke auswählen';
                        defaultOption.disabled = true;
                        defaultOption.selected = true;
                        brandSelect.appendChild(defaultOption);

                        // Populate the dropdown with filtered brand options
                        filteredBrands.forEach(brand => {
                            const option = document.createElement('option');
                            option.value = brand;
                            option.textContent = brand;
                            brandSelect.appendChild(option);
                        });

                        console.log(`Dropdown mit der ID "${targetId}" wurde erfolgreich gefüllt.`);
                    })
                    .catch(error => {
                        console.error('Fehler beim Abrufen der Fahrzeuge:', error);
                    });
            })
            .catch(error => {
                console.error('Fehler beim Abrufen der Einstellungen:', error);
            });
    }

    // Populate the non-recurring trip brand dropdown
    populateBrandDropdown('brand-select');

    // Populate the recurring trip brand dropdown
    populateBrandDropdown('brand-select-recurring');

    // Event Listener für das Einreichen des Non-recurring Trip Formulars
    const nonRecurringForm = document.getElementById('non-recurring-trip-form');
    if (nonRecurringForm) {
        nonRecurringForm.addEventListener('submit', function(event) { //submit instead of button worked
            event.preventDefault();

            // Sammeln der Formulardaten
            const brand = document.getElementById('brand-select').value;
            const departure_date = document.getElementById('departure-date').value;
            const departure_time = document.getElementById('departure-time').value;
            const return_date = document.getElementById('return-date').value;
            const return_time = document.getElementById('return-time').value;
            const distance = document.getElementById('distance').value;
            const description = document.getElementById('comment').value;

            if (!weekday || !departure_time || !departure_date || !return_time|| !return_date || !distance || !brand || !description) {
                alert('Please fill all the fields.');
                return;
            }

            // Erstellen des neuen Trips
            const newTrip = {
                brand,
                departure_date,
                departure_time,
                return_date,
                return_time,
                distance,
                description
            };

            // Senden des neuen Trips zu /add_non_recurring_trip
            fetch('/add_non_recurring_trip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newTrip)
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    alert('Trip hinzugefügt!');
                    nonRecurringForm.reset();
                    // Optional: Weitere Aktionen, z.B. UI-Update
                } else {
                    alert('Fehler beim Hinzufügen des Trips: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Fehler beim Senden des Trips:', error);
                alert('Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.');
            });
        });
    } else {
        console.error('Formular mit der ID "non-recurring-trip-form" nicht gefunden.');
    }

    // Event Listener für das Einreichen des Recurring Trip Formulars (falls vorhanden)
    const recurringForm = document.getElementById('recurring-trip-form');
    if (recurringForm) {
        recurringForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // Sammeln der Formulardaten
            const brand = document.getElementById('brand-select-recurring').value;
            const departure_date= document.getElementById('recurring-departure-date').value;
            const departure_time = document.getElementById('recurring-departure-time').value;
            const return_date = document.getElementById('recurring-return-date').value;
            const return_time = document.getElementById('recurring-return-time').value;
            const distance = document.getElementById('recurring-distance').value;
            const description = document.getElementById('recurring-comment').value;

            if (!brand || !departure_date || !departure_time || !return_date || !return_time || !distance || !description) {
                alert('Please fill all the fields.');
                return;
            }

            // Erstellen des neuen Trips
            const newTrip = {
                brand,
                departure_date,
                departure_time,
                return_date,
                return_time,
                distance: Number(distance),
                description
            };


            // Senden des neuen Trips zu /add_recurring_trip (angenommen, es gibt einen solchen Endpunkt)
            fetch('/add_recurring_trip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newTrip)
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    alert('Recurring Trip hinzugefügt!');
                    recurringForm.reset();
                    // Optional: Weitere Aktionen, z.B. UI-Update
                } else {
                    alert('Fehler beim Hinzufügen des Recurring Trips: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Fehler beim Senden des Recurring Trips:', error);
                alert('Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.');
            });
        });
    }

  

    // Optional: Öffnen des Popups bei Klick auf einen Button
    const addNonRecurringBtn = document.getElementById('add-non-recurring');
    if (addNonRecurringBtn && nonRecurringPopup) {
        addNonRecurringBtn.addEventListener('click', function() {
            nonRecurringPopup.style.display = 'block';
        });
    }

    // Schließen des Popups beim Klick außerhalb des Inhalts
    window.addEventListener('click', function(event) {
        if (event.target == nonRecurringPopup) {
            nonRecurringPopup.style.display = 'none';
        }
    }); 

    // Schließen des Popups beim Klick auf die Schließen-Schaltfläche
    const closeButtons = document.querySelectorAll('.btn-close');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            nonRecurringPopup.style.display = 'none';
        });
    });




// BUG: jQuery: n is not a function
    // Initialize ClockPicker (falls notwendig)
    $(document).on('focus', '.clockpicker', function() {
        $(this).clockpicker({
            autoclose: true
        });
    });

    // Fetch data from the Flask server
    fetch('/get_data')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            console.log('Fetched data:', data); // Debugging
            displayAllTrips(data);
        })
        .catch(error => console.error('Error fetching data:', error));

    // Open the recurring trip popup when "Weekly Trip" button is clicked
    const recurringPopup = document.getElementById('recurring-trip-popup');
    const addRecurringBtn = document.getElementById('add-weekly'); 
    if (addRecurringBtn) {
        addRecurringBtn.addEventListener('click', function() {
            recurringPopup.style.display = 'flex';
        });
    }
});

function displayAllTrips(data) {
    // Iterate over each brand in the data
    for (const brand in data) {
        if (data.hasOwnProperty(brand)) {
            // Erstellen Sie Sektionen für jede Marke, falls noch nicht vorhanden
            createBrandSection(brand);

            // Anzeigen der nicht-wiederkehrenden Fahrten
            displayTrips(data[brand].non_recurring, `${brand}-non-recurring-list`, 'Nicht-wiederkehrende Fahrten');

            // Anzeigen der wöchentlichen/wiederkehrenden Fahrten
            displayTrips(data[brand].recurring, `${brand}-recurring-list`, 'Wöchentliche Fahrten');
        }
    }
}

function createBrandSection(brand) {
    // Überprüfen, ob die Sektion für die Marke bereits existiert
    if (!document.getElementById(`${brand}-section`)) {
        const container = document.getElementById('trips-container');

        const brandSection = document.createElement('section');
        brandSection.id = `${brand}-section`;

        const brandHeader = document.createElement('h2');
        brandHeader.textContent = `${brand} - Fahrten`;
        brandSection.appendChild(brandHeader);

        // Nicht-wiederkehrende Fahrten
        const nonRecurringHeader = document.createElement('h3');
        nonRecurringHeader.textContent = 'Nicht-wiederkehrende Fahrten';
        brandSection.appendChild(nonRecurringHeader);

        const nonRecurringList = document.createElement('div');
        nonRecurringList.id = `${brand}-non-recurring-list`;
        brandSection.appendChild(nonRecurringList);

        
        // Wiederkehrende Fahrten
        const recurringHeader = document.createElement('h3');
        recurringHeader.textContent = 'Wöchentliche Fahrten';
        brandSection.appendChild(recurringHeader);

        const recurringList = document.createElement('div');
        recurringList.id = `${brand}-recurring-list`;
        brandSection.appendChild(recurringList);

        container.appendChild(brandSection);
    }
}

function displayTrips(trips, elementId, tripType) {
    console.log(`Displaying ${tripType} in ${elementId}:`, trips); // Debugging
    const listElement = document.getElementById(elementId);
    listElement.innerHTML = ''; // Clear existing content
    if (trips && trips.length > 0) {
        const rowElement = document.createElement('div');
        rowElement.className = 'row';

        trips.forEach(trip => {
            const tripElement = document.createElement('div');
            tripElement.className = 'col-lg-6 col-md-6 col-sm-12';

            let departureInfo = '';
            let returnInfo = '';

            if (tripType === 'Wöchentliche Fahrten') {
                // For weekly trips, display weekday and time
                departureInfo = `${trip.departure_date} ${trip.departure_time} Uhr`;
                returnInfo = trip.return_time ? `${trip.return_date} ${trip.return_time}` : '';
            } else {
                // Format dates for non-recurring trips
                departureInfo = `${formatDateTime(trip.departure_date, trip.departure_time).split(" ")[0]}&nbspum&nbsp${trip.departure_time}&nbspUhr`;
                returnInfo = trip.return_date ? `${formatDateTime(trip.return_date, trip.return_time).split(" ")[0]}&nbspum&nbsp${trip.return_time}&nbspUhr` : '';
                
            }
            
            tripElement.innerHTML = `
                <div class="alert alert-primary">
                    <div class="row">      
                        <div class="trip-actions text-center">
                            <svg onclick="deleteTrip('${trip.id}')" style="fill: var(--primary-color); cursor: pointer;" height="1em" version="1.1" viewBox="0 0 34.811 58.336" xmlns="http://www.w3.org/2000/svg">
                                <g transform="translate(-43.701 -148.27)">
                                <path d="m64.111 148.27c-0.02793 4.3e-4 -0.0533 1e-3 -0.07995 3e-3l-6.6012 0.43741c-0.86229 0.057-1.5102 0.79756-1.4532 1.6599l0.04303 0.6665c0.03098 0.46953 0.26478 0.87586 0.61045 1.1392l-11.922 0.7883c-0.59649 0.0393-1.044 0.5507-1.0046 1.1472l0.16186 2.4418c0.03933 0.5965 0.5507 1.044 1.1472 1.0046l32.493-2.1486c0.5965-0.0393 1.0441-0.55229 1.0046-1.1488l-0.16022-2.4402c-0.03933-0.59648-0.55229-1.0456-1.1488-1.0062l-11.92 0.7883c0.30695-0.30633 0.48441-0.73935 0.45341-1.2081l-0.04303-0.6665c-0.05522-0.83535-0.75234-1.471-1.5798-1.458zm-15.912 10.504c-1.0329 0-1.8338 0.89677-1.7977 1.929l1.5397 44.104c0.03596 1.0323 0.89517 1.8337 1.9275 1.7977h23.785c1.0323 0.036 1.893-0.76539 1.929-1.7977l1.5397-44.104c0.03596-1.0323-0.76537-1.893-1.7977-1.929zm13.563 5.1542c0.86419 0 1.5589 0.69636 1.5589 1.5605v34.251c0 0.86418-0.69475 1.5606-1.5589 1.5606-0.86419 0-1.5606-0.69638-1.5606-1.5606v-34.251c0-0.86418 0.69637-1.5605 1.5606-1.5605zm-8.5207 0.0128c0.86366-0.031 1.5832 0.64081 1.6134 1.5045l1.1968 34.229c0.03099 0.86367-0.64242 1.5832-1.5061 1.6134-0.86367 0.031-1.5832-0.64081-1.6134-1.5045l-1.1953-34.229c-0.03098-0.86367 0.6408-1.5833 1.5045-1.6134zm17.04 0c0.86367 0.031 1.5346 0.74976 1.5045 1.6134l-1.1953 34.229c-0.03099 0.86365-0.74975 1.5346-1.6134 1.5045-0.86366-0.031-1.5346-0.74975-1.5045-1.6134l1.1953-34.229c0.03098-0.86366 0.74975-1.5346 1.6134-1.5045z" stroke-linecap="round" stroke-linejoin="round" stroke-width=".070635"/>
                                </g>
                            </svg>

            
                            <svg onclick="editTrip('${trip.id}')" style="fill: var(--primary-color); cursor: pointer;" height="1em"  version="1.1" viewBox="0 0 109.06 58.286" xmlns="http://www.w3.org/2000/svg">
                                <g transform="translate(-43.72 -148.28)">
                                <g transform="matrix(1.6776 0 0 1.6776 -21.748 -106.83)">
                                <g transform="matrix(.62098 -.62098 .75489 .75489 -120.83 116.72)">
                                    <path d="m128.77 159.48v6.8024h6.976s0.91978 0.0614 1.3429-0.36175c1.6033-1.6034 1.8068-4.4077 0.20348-6.0111-0.49847-0.49847-1.8661-0.42958-1.8661-0.42958z" stroke-width=".89905" style="-inkscape-stroke:none"/>
                                    <path d="m101.33 159.48-3.7205 3.2442 3.7205 3.5605h25.778v-6.8047z" stroke-width=".88102" style="-inkscape-stroke:none"/>
                                </g>
                                <path d="m54.742 157.95v28.781h28.781v-20.957l-4 4.1248v12.832h-20.781v-20.781h14.189l3.805-4z" style="-inkscape-stroke:none"/>
                                </g>
                                </g>
                                
                            </svg>

                        </div>  
                        <div class="col-md-6 col-sm-12 col-sm-12  text-center">            
                            <svg  style="fill: var(--secondary-color);" height="1em"  version="1.1" viewBox="0 0 109.06 58.286" xmlns="http://www.w3.org/2000/svg">
                                <g transform="translate(-43.72 -148.28)">
                                <g transform="matrix(.1328 0 0 .1328 38.097 111.58)">
                                <path d="m437.15 499.44m0 0-162.81-144.19-162.91 144.25v206.12c0 5.3234 4.3016 9.5938 9.625 9.5938h101.81v-90.375c0-5.3234 4.2704-9.625 9.5938-9.625h83.656c5.3234 0 9.5938 4.3016 9.5938 9.625v90.375h101.84c5.3234 0 9.5938-4.2704 9.5938-9.5938v-206.19z"/>
                                <path d="m273.39 276.34-231.05 204.58 24.338 27.457 207.66-183.88 207.61 183.88 24.291-27.457-231-204.58-0.89792 1.0397-0.94518-1.0397z"/>
                                <path d="m111.43 305.79h58.571l-0.51038 34.691-58.061 52.452v-87.143z"/>
                                </g>
                                <path d="m117.01 185.58c-0.29072 0.16306-0.53803 0.39976-0.71441 0.69875l-3.3509 5.3482c-0.20653 0.36015-0.5032 0.64269-0.86315 0.85135-0.14724 0.0854-0.31706 0.1611-0.48329 0.21373l-3.2116 1.0552c-0.69757 0.2295-1.1579 0.87014-1.1558 1.5903l2e-3 4.9792c0.0152 0.9311 0.75202 1.6863 1.6668 1.6807l4.2574-0.0202c-0.20536 0.9278-0.0699 1.8762 0.41383 2.7106 2.1528 3.7138 7.8576 1.4502 6.8955-2.7354l20.457-0.0279c-0.189 0.91831-0.0604 1.8925 0.41382 2.7106 2.1528 3.7138 7.8614 1.4573 6.8997-2.7284l2.879-9e-3c0.98282-1e-3 1.7669-0.87344 1.6458-1.8742l-0.63911-5.2269c-0.0415-0.26011-0.12633-0.51255-0.2591-0.7416-0.32245-0.55624-0.90987-0.92336-1.5576-0.98499l-10.053-0.86117c-0.53751-0.06-1.0417-0.32763-1.3822-0.76415l-4.2267-5.3765c-0.38528-0.47612-0.97498-0.77378-1.5848-0.77001l-15.088 0.0272c-0.33894-2.5e-4 -0.67181 0.0913-0.96253 0.25436zm1.6825 3.0662 5.0004-0.0147 2e-3 3.8503-7.4768-2e-3 2.4736-3.8341zm8.5588 0.0193 5.1552-0.01 3.0115 3.8042-8.1587 0.0332-8e-3 -3.8279z" stroke-width=".047187"/>
                                </g>
                            </svg>
                            <br>

                        ${departureInfo}
                        </div>
                        ${returnInfo ? `
                        <div class="col-lg-6 col-md-6 col-sm-12 text-center">
                            <svg style="fill: var(--secondary-color);" height="1em"  version="1.1" viewBox="0 0 109.06 58.286" xmlns="http://www.w3.org/2000/svg">
                                <g transform="translate(-43.72 -148.28)">
                                <g transform="matrix(.1328 0 0 .1328 38.097 111.58)">
                                <path d="m437.15 499.44m0 0-162.81-144.19-162.91 144.25v206.12c0 5.3234 4.3016 9.5938 9.625 9.5938h101.81v-90.375c0-5.3234 4.2704-9.625 9.5938-9.625h83.656c5.3234 0 9.5938 4.3016 9.5938 9.625v90.375h101.84c5.3234 0 9.5938-4.2704 9.5938-9.5938v-206.19z"/>
                                <path d="m273.39 276.34-231.05 204.58 24.338 27.457 207.66-183.88 207.61 183.88 24.291-27.457-231-204.58-0.89792 1.0397-0.94518-1.0397z"/>
                                <path d="m111.43 305.79h58.571l-0.51038 34.691-58.061 52.452v-87.143z"/>
                                </g>
                                <path d="m143 185.58c0.29072 0.16306 0.53803 0.39976 0.71441 0.69875l3.3509 5.3482c0.20653 0.36015 0.5032 0.64269 0.86315 0.85135 0.14724 0.0854 0.31706 0.1611 0.48329 0.21373l3.2116 1.0552c0.69757 0.2295 1.1579 0.87014 1.1558 1.5903l-2e-3 4.9792c-0.0152 0.9311-0.75202 1.6863-1.6668 1.6807l-4.2574-0.0202c0.20536 0.9278 0.0699 1.8762-0.41383 2.7106-2.1528 3.7138-7.8576 1.4502-6.8955-2.7354l-20.457-0.0279c0.189 0.91831 0.0604 1.8925-0.41382 2.7106-2.1528 3.7138-7.8614 1.4573-6.8997-2.7284l-2.879-9e-3c-0.98282-1e-3 -1.7669-0.87344-1.6458-1.8742l0.63911-5.2269c0.0415-0.26011 0.12633-0.51255 0.2591-0.7416 0.32245-0.55624 0.90987-0.92336 1.5576-0.98499l10.053-0.86117c0.53751-0.06 1.0417-0.32763 1.3822-0.76415l4.2267-5.3765c0.38528-0.47612 0.97498-0.77378 1.5848-0.77001l15.088 0.0272c0.33894-2.5e-4 0.67181 0.0913 0.96253 0.25436zm-1.6825 3.0662-5.0004-0.0147-2e-3 3.8503 7.4768-2e-3 -2.4736-3.8341zm-8.5588 0.0193-5.1552-0.01-3.0115 3.8042 8.1587 0.0332 8e-3 -3.8279z" stroke-width=".047187"/>
                                </g>
                            </svg>
                            <br>
                        ${returnInfo}
                        </div>` : '</div>'}
                        ${trip.description ? `
                        <div class="col-lg-6 col-md-6 col-sm-12 text-center">
                            <svg style="fill: var(--secondary-color);" height="1em"   version="1.1" viewBox="0 0 109.06 58.286" xmlns="http://www.w3.org/2000/svg">
                                <g transform="translate(-43.72 -148.28)">
                                <path d="m55.512 148.35c-6.512 0-11.792 5.2796-11.792 11.792s11.792 30.27 11.792 30.27 11.792-23.758 11.792-30.27-5.2792-11.792-11.792-11.792zm0 17.025c-2.8901 0-5.2334-2.3437-5.2334-5.2334 0-2.8896 2.3433-5.2334 5.2334-5.2334 2.8901 0 5.2334 2.3429 5.2334 5.2334 0 2.8905-2.3428 5.2334-5.2334 5.2334z" stroke-width=".42062"/>
                                <path d="m140.15 157.85c-7.0665 0-12.796 5.7291-12.796 12.796 0 7.0665 12.796 32.848 12.796 32.848s12.796-25.781 12.796-32.848c0-7.0669-5.7287-12.796-12.796-12.796zm0 18.475c-3.1361 0-5.6789-2.5432-5.6789-5.6789 0-3.1357 2.5428-5.6789 5.6789-5.6789 3.1362 0 5.6789 2.5423 5.6789 5.6789 0 3.1366-2.5423 5.6789-5.6789 5.6789z" stroke-width=".45643"/>
                                <path d="m55.742 193.56c19.83 6.5921 13.024-14.297 26.065-24.395 3.7766-0.75736 8.2333 0.61124 9.8437 4.3716 2.919 5.7471 1.8588 13.239 6.6127 18.069 2.5836 1.7289 5.4367 3.2714 8.5247 3.9201 6.355 1.2699 13.447-1.2123 19.273 2.3937 3.3524 1.9029 3.57 5.5783 7.9326 5.9288 1.6153 0.31784 3.8403 0.2534 5.3948-0.31227" fill="none"  stroke=var(--secondary-color)  stroke-dasharray="10.13,5.065" stroke-width="5.065"/>
                                </g>
                            </svg>
                            <br>
                            ${trip.distance} km
                        </div>` : '</div>'}
                    </div> <!-- row -->
                    <div class="row">
                        <div class="col-lg-6 col-md-6 col-sm-12 text-center">
                            <svg style="fill: var(--secondary-color);" height="1em" version="1.1" viewBox="0 0 109.06 58.286" xmlns="http://www.w3.org/2000/svg">
                                <g transform="translate(-43.72 -148.28)">
                                <path d="m83.65 201.05c6.5211-1.3382 10.387 4.5112 0.94961 4.4449-3.0579-0.0215-1.4716-0.0613-2.3414-0.12148-1.0935-0.0756-2.2034-0.67191-2.6265-2.5642-1.0408-5.7995 0.09351-11.727-0.16206-17.579-1.4794-3.9187-3.9083 3.6398-5.8262 4.9424-4.5899 6.0012-10.212 12.298-18.459 14.697-4.8157 1.923-11.509-0.72041-10.291-5.7565 1.9265-7.965 8.0382-14.66 13.899-20.868 4.3839-4.0688 9.0476-8.6368 15.486-10.204 5.6069-0.51684 9.2087 5.4158 6.5499 9.38-2.0515 1.9908 3.2441-0.48182 2.0175 2.7569 0.28718 6.5761 0.48164 14.297 0.80475 20.872zm-31.565 0.23089c8.4435-0.25662 14.147-6.5672 18.624-11.951 3.1083-4.5265 8.3028-8.824 7.5028-14.493-0.51499-6.6653-8.2002-2.2829-12.322 1.4028-6.7392 6.1632-13.328 13.046-16.124 21.262-0.47167 1.5333-0.23334 3.9712 2.3193 3.7806zm73.687-25.978c-0.4981 9.5743-8.15 17.531-16.005 23.817-3.8605 2.2475-8.0493 7.3863-13.056 5.742-1.9879-5.2571 7.795-5.2835 10.748-8.6497 7.0777-5.0232 13.44-11.983 14.11-20.071-1.0667-5.7822-10.007-1.6132-12.843 1.0904-7.748 6.3011-12.078 15.037-14.53 23.769-5.6312 4.4904-4.7455-5.293-4.7231-8.2234-0.38344-13.117-0.76575-26.242-1.7038-39.338-2.7282-3.634 3.1159-6.5561 4.2753-1.9903 1.1213 4.709 0.26395 9.6088 0.58322 14.397 0.2731 8.555-0.1412 17.205 1.3113 25.684 3.9115-8.2878 10.297-16.311 19.618-20.765 4.5864-2.9995 12.94-1.0917 12.215 4.5379zm26.006 12.722c-3.839 6.0513-9.2933 11.516-15.805 15.608-4.9062 3.2356-12.516 0.84682-13.312-4.4972-1.0949-7.231 2.4152-14.333 5.7067-20.845 3.0382-4.7077 6.2334-10.677 12.859-12.197 6.0852-0.90163 8.5125 6.2224 5.5439 9.7419-2.8317-1.3376-0.22737-8.7447-5.9757-5.5399-5.9523 3.4264-8.6663 9.5825-11.142 15.079-1.5348 4.6829-4.2757 9.9504-1.8387 14.725 3.8538 3.1571 9.4687-0.32535 12.499-2.8533 3.8508-2.9976 6.9009-6.6971 10.392-9.9073 0.50431-0.10878 1.1227 0.23075 1.073 0.68564z" stroke-width="1.4917" aria-label="abc"/>
                                </g>
                            </svg>
                            ${trip.description}
                        </div>
                    </div> <!-- row -->
                </div> <!-- alert alert-primary -->

            `;
            rowElement.appendChild(tripElement);
        });

        listElement.appendChild(rowElement);
    } else {
        listElement.innerHTML = '<p>Keine Fahrten gefunden.</p>';
    }
}

function formatDateTime(dateStr, timeStr) {
    const dateParts = dateStr.split('-'); // Assuming date in 'yyyy-mm-dd' format
    const formattedDate = `${dateParts[2]}.${dateParts[1]}.${dateParts[0]}`; // 'tt.mm.jjjj'
    return `${formattedDate} ${timeStr}`;
}





// Add functionality to initialize the clock picker when time fields are clicked
$(document).on('focus', '.clockpicker', function() {
    $(this).clockpicker({
        autoclose: true
    });
});

// ---------------- Non-recurring trip logic --------------------

const nonRecurringPopup = document.getElementById('non-recurring-trip-popup');
const closeNonRecurringPopupBtn = document.querySelector('.close');
const addNonRecurringBtn = document.getElementById('add-non-recurring');
const nonRecurringForm = document.getElementById('non-recurring-trip-form');

// Open the popup when "Non-recurring Trip" button is clicked
addNonRecurringBtn.addEventListener('click', function() {
    nonRecurringForm.reset();  // This resets all form fields to empty values

    // Reset Flatpickr and ClockPicker for departure and return
    flatpickr('#departure-date').clear();  // Clears the Flatpickr input
    flatpickr('#return-date').clear();  // Clears the return date
    $('#departure-time').val('');  // Clears the ClockPicker input
    $('#return-time').val('');  // Clears the return time

    nonRecurringPopup.style.display = 'flex';  // Show the popup
});

// FIXME: delete if code is working
/* // Close the non-recurring trip popup
closeNonRecurringPopupBtn.addEventListener('click', function() {
    nonRecurringPopup.style.display = 'none';  // Hide the popup
}); */

// Close the recurring trip popup when the close button is clicked
document.querySelector('.btn-close').addEventListener('click', function() {
    console.log('Close button clicked');
    recurringPopup.style.display = 'none';
    nonRecurringPopup.style.display = 'none';

});

// Initialize Flatpickr for the date picker (departure and return)
flatpickr('#departure-date', { dateFormat: 'Y-m-d', minDate: 'today' });
flatpickr('#return-date', { dateFormat: 'Y-m-d', minDate: 'today' });

// Handle form submission for adding a new non-recurring trip
nonRecurringForm.addEventListener('submit', function(event) {
    event.preventDefault();
    console.log('Add Trip Button clicked');


    // Erfassen der Formulardaten
    const departure_date= document.getElementById('departure-date').value;
    const departure_time = document.getElementById('departure-time').value;
    const return_date = document.getElementById('return-date').value;
    const return_time= document.getElementById('return-time').value;
    const distance = document.getElementById('distance').value;
    const description = document.getElementById('description').value;

    // Marke erfassen
    const brand = document.getElementById('brand-select').value;

    // Neues Fahrtdatenobjekt erstellen
    const newTrip = {
        departure: departure_date,
        departure_time: departure_time,
        return: return_date,
        return_time: return_time,
        distance: parseFloat(distance),
        description: description,
        brand: brand
    };

    // Senden der neuen Fahrtdaten an das Backend
    fetch('/add_non_recurring_trip', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(newTrip)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            console.log('Trip added:', data);
            // Aktualisieren Sie die Anzeige der Fahrten oder laden Sie die Daten neu
        } else {
            console.error('Error adding trip:', data.error);
            alert('Error adding trip: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error adding trip:', error);
        alert('Error adding trip: ' + error);
    });
});

// ---------------- Recurring trip logic --------------------


const closeRecurringPopupBtn = document.getElementById('close-recurring-popup');
 // Corrected button ID to match HTML
const recurringForm = document.getElementById('recurring-trip-form');

// Open the recurring trip popup when "Weekly Trip" button is clicked
const recurringPopup = document.getElementById('recurring-trip-popup');
const addRecurringBtn = document.getElementById('add-weekly'); 
if (addRecurringBtn) {
    addRecurringBtn.addEventListener('click', function() {
        recurringPopup.style.display = 'flex';
    });
}


// Close the recurring trip popup

closeRecurringPopupBtn.addEventListener('click', function() {
    recurringPopup.style.display = 'none';  // Hide the popup
});

// Close the recurring trip popup when clicked outside the content
window.addEventListener('click', function(event) {
    if (event.target == recurringPopup) {
        recurringPopup.style.display = 'none';
    }
});

// Handle form submission for adding a new recurring trip
recurringForm.addEventListener('submit', function(event) {
    event.preventDefault();

    // Sammeln der Formulardaten
    const weekday = document.getElementById('weekday').value;
    const departure_time = document.getElementById('recurring-departure-time').value;
    const return_time = document.getElementById('recurring-return-time').value;
    const distance = document.getElementById('recurring-distance').value;
    const brand = document.getElementById('brand-select-recurring').value;
    const description = document.getElementById('recurring-description').value;

    // Überprüfen, ob alle Felder ausgefüllt sind
    if (!weekday || !departure_time || !return_time || !distance || !brand || !description) {
        alert('Please fill all the fields.');
        return;
    }

    const newRecurringTrip = {
        departure: weekday,
        departure_time: departure_time,
        return: weekday,
        return_time: return_time,
        distance: Number(distance),
        brand: brand,
        description: description
    };

    fetch('/add_recurring_trip', {
        // BUG: For both recurring and non recurring trips the distance must be a number not a string
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRecurringTrip)
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert('Recurring trip added successfully!');
            recurringPopup.style.display = 'none';  // Close the popup
        } else {
            alert('Error adding trip: ' + result.message);
        }
    })
    .catch(error => {
        alert('Network error: ' + error.message);
    });
});

// ---------------- Fetch and update trip data --------------------
function fetchTripsAndUpdateUI() {
    fetch('/get_data')
        .then(response => response.json())
        .then(data => {
            // Löschen Sie die aktuelle Anzeige
            document.getElementById('trips-container').innerHTML = '';
            // Aktualisieren Sie die Anzeige mit den neuen Daten
            displayAllTrips(data);
        })
        .catch(error => console.error('Error fetching data:', error));
}


function editTrip(tripId) {
    // open info badge
    document.getElementById('edit-trip-form').style.display = 'block';
    // TODO: make an edit trip modal
/*     // Fetch the trip data using the tripId
    fetch(`/get_trip/${tripId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const trip = data.trip;
                // Populate the form fields with the trip data
                document.getElementById('trip-id').value = trip.id;
                document.getElementById('brand-select').value = trip.brand;
                document.getElementById('departure-date').value = trip.departure_Dated
                document.getElementById('departure-time').value = trip.departure_time;
                document.getElementById('return-date').value = trip._deturnDate;
                document.getElementById('return-time').value = trip._t
                document.getElementById('distance').value = trip.distance;
                document.getElementById('description').value = trip.description;
                document.getElementById('comment').value = trip.comment;
                // Show the form for editing
                document.getElementById('trip-form').style.display = 'block';
            } else {
                alert('Error fetching trip data: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred. Please try again later.');
        }); */
}

function saveEditedTrip() {
    const tripId = document.getElementById('trip-id').value;
    const updatedTrip = {
        id: tripId,
        brand: document.getElementById('brand-select').value,
        departure_date: document.getElementById('departure-date').value,
        departure_time: document.getElementById('departure-time').value,
        return_date: document.getElementById('return-date').value,
        return_time: document.getElementById('return-time').value,
        distance: document.getElementById('distance').value,
        description: document.getElementById('description').value,
        comment: document.getElementById('comment').value
    };

    fetch('/edit_trip', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(updatedTrip)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            alert('Trip updated successfully!');
            document.getElementById('trip-form').style.display = 'none';
            // Refresh the trip list
            fetchTripsAndUpdateUI();
        } else {
            alert('Error updating trip: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred. Please try again later.');
    });
}

function deleteTrip(tripId) {
    if (confirm('Are you sure you want to delete this trip?')) {
        fetch('/delete_trip', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: tripId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                alert('Trip deleted successfully!');
                // Refresh the trip list
                fetchTripsAndUpdateUI();
            } else {
                alert('Error deleting trip: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred. Please try again later.');
        });
    }
}

// ---------------- Displaying all the time series using chart.js --------------------
// Create a canvas element inside the div
const ctx = document.createElement('canvas');
document.getElementById('json-time-series').appendChild(ctx);

// Fetch the JSON data
fetch('/templates/time_series_data.json')
    .then(response => {
        return response.json();
    })
    .then(data => {
        console.log('Fetched time series json:', data);
        
        // Extract datasets from the fetched data
        const labels = data.trips ? data.trips.map(entry => entry.datetime) : [];
        const hourly_climate_energy = data.hourly_climate_energy || [];
        const hourly_energy_surplus = data.hourly_energy_surplus || [];
        const electricity_prices = data.electricity_prices || [];
        const home_battery_energy_forecast = data.home_battery_energy_forecast || [];
        const grid_feedin = data.grid_feedin || [];
        const required_charge = data.required_charge || [];
        const charging_plan = data.charging_plan || [];
        const usable_energy_for_ev = data.usable_energy_for_ev || [];
        const solar_forecast = data.solar_forecast || [];
        const future_grid_feedin = data.future_grid_feedin || [];
        const weather_forecast = data.weather_forecast || [];


        // Create the chart
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Heating house',
                        data: hourly_climate_energy.map(entry => ({ x: entry.time, y: entry.climate_energy_corrected })),
                        borderColor: 'rgb(255, 94, 0)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Baseload house',
                        data: hourly_climate_energy.map(entry => ({ x: entry.time, y: entry.baseload })),
                        borderColor: 'rgb(207, 59, 0)',
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Hourly Energy Surplus',
                        data: hourly_energy_surplus.map(entry => ({ x: entry.time, y: entry.energy_surplus })),
                        borderColor: 'rgb(115, 255, 0)',
                        fill: true,
                        yAxisID: 'y0',
                        tension: 0.4,
                        borderDash: [5, 5]
                    },
                    {
                        label: 'Electricity Prices',
                        data: electricity_prices.map(entry => ({ x: entry.start, y: entry.total })),
                        borderColor: 'rgba(54, 162, 235, 1)',
                        fill: false,
                        yAxisID: 'y1',
                        stepped: 'before', // Added for stepped lines
                        tension: 0 // Ensures sharp lines
                    },
                    {
                        label: 'Home Battery Energy Forecast',
                        data: home_battery_energy_forecast.map(entry => ({ x: entry.time, y: entry.forecast })),
                        borderColor: 'rgb(204, 0, 255)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Grid Feed-in',
                        data: grid_feedin.map(entry => ({ x: entry.time, y: entry.feedin })),
                        borderColor: 'rgb(38, 133, 88)',
                        borderDash: [5, 5],
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Home battery charging',
                        data: required_charge.map(entry => ({ x: entry.time, y: entry.charge })),
                        borderColor: 'rgba(75, 192, 192, 0.5)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Charging Plan',
                        data: charging_plan.map(entry => ({ x: entry.time, y: entry.plan })),
                        borderColor: 'rgba(255, 99, 132, 0.5)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Usable Energy for EV',
                        data: usable_energy_for_ev.map(entry => ({ x: entry.time, y: entry.pv_estimate })),
                        borderColor: 'rgba(153, 102, 255, 0.5)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Solar Forecast',
                        data: solar_forecast.map(entry => ({ x: entry.time, y: entry.pv_estimate })),
                        borderColor: 'rgb(255, 244, 85)',
                        backgroundColor: 'rgb(255, 248, 144)',
                        fill: true,
                        yAxisID: 'y0',
                        pointStyle: 'crossRot',
                        tension: 0.4
                    },
                    {
                        label: 'Future Grid Feed-in',
                        data: future_grid_feedin.map(entry => ({ x: entry.time, y: entry.feedin })),
                        borderColor: 'rgba(27, 190, 54, 0.5)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    },
                    {
                        label: 'Weather Forecast',
                        data: weather_forecast.map(entry => ({ x: entry.dt, y: entry.temp*100 })),
                        borderColor: 'rgba(255, 99, 132, 0.5)',
                        fill: false,
                        yAxisID: 'y0',
                        tension: 0.4
                    }
                ]
            },
            options: {
                // TODO: does not work like this or getting it from the browser  maybe at wrong position? locale: 'de-DE', // Automatically set locale based on user's browser settings
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                hour: 'MMM d, HH:mm' // Display date and time in 24-hour format
                            }
                            //tooltipFormat: 'll HH:mm'
                        },
                        title: {
                            display: true,
                            text: 'Date and Time'
                        }
                    },
                    y0: { // Changed from '0' to 'y0'
                        title: {
                            display: true,
                            text: 'Energy (Wh) / c°C'
                        },
                        position: 'left'
                    },
                    y1: { // Changed from additional y-axes to only 'y1'
                        title: {
                            display: true,
                            text: 'Price (€/kWh)',
                            
                        },
                        position: 'right'
                    }
                }
            }
        });
    })
    .catch(error => {
        console.error('Error fetching time series data:', error);
    });


function holidayMode() {
    // Create toggle switch container
    const container = document.getElementById('holiday-mode-container');
    if (!container) {
        console.error('Container for Holiday Mode toggle not found.');
        return;
    }

    // Create label for toggle
    const label = document.createElement('label');
    label.className = 'switch';
    label.innerHTML = `
        <input type="checkbox" id="holiday-toggle">
        <span class="slider round"></span>
    `;
    container.appendChild(label);

    const toggle = document.getElementById('holiday-toggle');

    // Fetch current Holiday Mode setting
    fetch('/load_settings')
        .then(response => response.json())
        .then(settings => {
            const isHoliday = settings.HolidayMode.HOLIDAY_MODE === 'true';
            toggle.checked = isHoliday;
        })
        .catch(error => console.error('Error fetching settings:', error));

    // Handle toggle change
    toggle.addEventListener('change', function() {
        const newValue = this.checked;
        fetch('/update_holiday_mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ HOLIDAY_MODE: Boolean(newValue) }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                alert('Holiday Mode updated successfully!');
            } else {
                alert('Error updating Holiday Mode: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error updating Holiday Mode:', error);
            alert('An error occurred. Please try again later.');
        });
    });
}

// Initialize Holiday Mode toggle
holidayMode();

/* // ---------------- Fetch and update trip data --------------------
function fetchTripsAndUpdateUI() {
    fetch('/get_data')
        .then(response => response.json())
        .then(data => {
            // Löschen Sie die aktuelle Anzeige
            document.getElementById('trips-container').innerHTML = '';
            // Aktualisieren Sie die Anzeige mit den neuen Daten
            displayAllTrips(data);
        })
        .catch(error => console.error('Error fetching data:', error));
}
 */

/* FIXME: seems to be redundant */
/* function fetchTripsAndUpdateUI() {
    fetch('/get_data')
        .then(response => response.json())
        .then(data => {
            // Clear existing trip lists
            document.getElementById('non-recurring-list').innerHTML = '';
            document.getElementById('recurring-list').innerHTML = '';
            displayTrips(data.non_recurring, 'non-recurring-list', 'Nicht-wiederkehrende Fahrten');
            displayTrips(data.recurring, 'recurring-list', 'Wöchentliche Fahrten');
        })
        .catch(error => console.error('Error fetching data:', error));
} */