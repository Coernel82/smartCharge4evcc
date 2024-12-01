document.addEventListener('DOMContentLoaded', function() {
    // Load data from the server running on port 5000
    fetch('http://127.0.0.1:5000/get_data')
        .then(response => response.json())
        .then(data => {
            populateTrips(data);
            populateLoadNowOptions(data);
        })
        .catch(error => console.error('Error fetching data:', error));

    let hoverTimer;  // Declare a timer variable for the hover delay

    // Plus button hover menu logic
    document.getElementById('add-trip-btn').addEventListener('mouseover', function() {
        clearTimeout(hoverTimer);  // Clear any existing timers when mouse enters
        document.getElementById('add-trip-menu').style.display = 'block';  // Show the menu
    });

    document.getElementById('add-trip-btn').addEventListener('mouseleave', function() {
        hoverTimer = setTimeout(function() {
            document.getElementById('add-trip-menu').style.display = 'none';  // Hide the menu after delay
        }, 300);  // Adjust the delay time (300 ms in this case)
    });

    document.getElementById('add-trip-menu').addEventListener('mouseover', function() {
        clearTimeout(hoverTimer);  // Keep the menu open when hovering over the menu
    });

    document.getElementById('add-trip-menu').addEventListener('mouseleave', function() {
        hoverTimer = setTimeout(function() {
            document.getElementById('add-trip-menu').style.display = 'none';  // Hide the menu after delay
        }, 300);  // Adjust the delay time (300 ms in this case)
    });

    // Function to populate the trips in the respective sections
    function populateTrips(data) {
        const nonRecurringList = document.getElementById('non-recurring-list');
        const weeklyList = document.getElementById('weekly-list');

        // Clear existing content
        nonRecurringList.innerHTML = '';
        weeklyList.innerHTML = '';

        // Populate Non-recurring Trips
        data.non_recurring.forEach(trip => {
            const card = createTripCard(trip, 'non-recurring');
            nonRecurringList.appendChild(card);
        });

        // Populate Weekly/Recurring Trips
        data.recurring.forEach(trip => {
            const card = createTripCard(trip, 'recurring');
            weeklyList.appendChild(card);
        });
    }

    // Create the trip cards for both non-recurring and recurring trips
    function createTripCard(trip, type) {
        const card = document.createElement('div');
        card.className = 'trip-card';

        const table = document.createElement('table');
        const tbody = document.createElement('tbody');
        const row = document.createElement('tr');
        
        // Departure Icon
        const depIcon = document.createElement('td');
        depIcon.innerHTML = '<img src="icons/house_out.svg" class="icon">';
        row.appendChild(depIcon);

        // Departure time and date
        const depTime = document.createElement('td');
        if (type === 'non-recurring') {
            depTime.textContent = `${trip.departure_date} ${trip.departure_time}`;
        } else {
            depTime.textContent = `${trip.departure} ${trip.departure_time}`;
        }
        row.appendChild(depTime);

        // Return Icon
        const retIcon = document.createElement('td');
        retIcon.innerHTML = '<img src="icons/house_in.svg" class="icon">';
        row.appendChild(retIcon);

        // Return time and date
        const retTime = document.createElement('td');
        if (type === 'non-recurring') {
            retTime.textContent = `${trip.return_date} ${trip.return_time}`;
        } else {
            retTime.textContent = `${trip.return} ${trip.return_time}`;
        }
        row.appendChild(retTime);

        // Car Icon
        const carIcon = document.createElement('td');
        carIcon.innerHTML = '<img src="icons/car.svg" class="icon">';
        row.appendChild(carIcon);

        // Distance (in km)
        const distance = document.createElement('td');
        distance.textContent = `${trip.distance} km`;
        row.appendChild(distance);

        // Append row to table
        tbody.appendChild(row);
        table.appendChild(tbody);
        card.appendChild(table);

        return card;
    }

    // Populate the Load Now options for car and loadpoints
    function populateLoadNowOptions(data) {
        const carMenu = document.getElementById('car-menu');
        carMenu.innerHTML = ''; // Clear any previous content

        data.cars.forEach(car => {
            const carItem = document.createElement('div');
            carItem.textContent = car;
            carItem.classList.add('car-item');
            
            const loadpointMenu = document.createElement('div');
            loadpointMenu.classList.add('submenu');
            
            carItem.addEventListener('mouseover', () => {
                loadpointMenu.style.display = 'block';
            });
            
            carItem.addEventListener('mouseleave', () => {
                loadpointMenu.style.display = 'none';
            });

            data.loadpoints.forEach(loadpoint => {
                const loadpointItem = document.createElement('div');
                loadpointItem.textContent = loadpoint;
                loadpointItem.classList.add('loadpoint-item');
                loadpointItem.addEventListener('click', () => {
                    startLoadNow(car, loadpoint);
                });
                loadpointMenu.appendChild(loadpointItem);
            });

            carMenu.appendChild(carItem);
            carMenu.appendChild(loadpointMenu);
        });
    }

    // Start Load Now functionality
    function startLoadNow(car, loadpoint) {
        fetch('/load_now', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ car, loadpoint })
        })
        .then(response => response.json())
        .then(data => {
            alert('Load Now started!');
        });
    }

    // Add functionality to initialize the clock picker when time fields are clicked
    $(document).on('focus', '.clockpicker', function() {
        $(this).clockpicker({
            autoclose: true
        });
    });

    // ---------------- Non-recurring trip logic --------------------

    const nonRecurringPopup = document.getElementById('non-recurring-trip-popup');
    const closeNonRecurringPopupBtn = document.getElementById('close-popup');
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

    // Close the non-recurring trip popup
    closeNonRecurringPopupBtn.addEventListener('click', function() {
        nonRecurringPopup.style.display = 'none';  // Hide the popup
    });

    // Initialize Flatpickr for the date picker (departure and return)
    flatpickr('#departure-date', { dateFormat: 'Y-m-d', minDate: 'today' });
    flatpickr('#return-date', { dateFormat: 'Y-m-d', minDate: 'today' });

    // Handle form submission for adding a new non-recurring trip
    nonRecurringForm.addEventListener('submit', function(event) {
        event.preventDefault();

        const departureDate = document.getElementById('departure-date').value;
        const departureTime = document.getElementById('departure-time').value;
        const returnDate = document.getElementById('return-date').value;
        const returnTime = document.getElementById('return-time').value;
        const distance = document.getElementById('distance').value;

        if (!departureDate || !departureTime || !returnDate || !returnTime || !distance) {
            alert('Please fill all the fields.');
            return;
        }

        const newTrip = {
            departure_date: departureDate,
            departure_time: departureTime,
            return_date: returnDate,
            return_time: returnTime,
            distance: parseInt(distance)
        };

        fetch('http://127.0.0.1:5000/add_non_recurring_trip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newTrip)
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                alert('Non-recurring trip added successfully!');
                nonRecurringPopup.style.display = 'none';  // Close the popup
            } else {
                alert('Error adding trip: ' + result.message);
            }
        })
        .catch(error => {
            alert('Network error: ' + error.message);
        });
    });

    // ---------------- Recurring trip logic --------------------

    const recurringPopup = document.getElementById('recurring-trip-popup');
    const closeRecurringPopupBtn = document.getElementById('close-recurring-popup');
    const addRecurringBtn = document.getElementById('add-weekly');  // Corrected button ID to match HTML
    const recurringForm = document.getElementById('recurring-trip-form');

    // Open the recurring trip popup when "Weekly Trip" button is clicked
    addRecurringBtn.addEventListener('click', function() {
        recurringForm.reset();  // Reset all form fields

        $('#recurring-departure-time').val('');  // Clear departure time
        $('#recurring-return-time').val('');  // Clear return time

        recurringPopup.style.display = 'flex';  // Show the popup
    });

    // Close the recurring trip popup
    closeRecurringPopupBtn.addEventListener('click', function() {
        recurringPopup.style.display = 'none';  // Hide the popup
    });

    // Handle form submission for adding a new recurring trip
    recurringForm.addEventListener('submit', function(event) {
        event.preventDefault();

        const weekday = document.getElementById('weekday').value;
        const departureTime = document.getElementById('recurring-departure-time').value;
        const returnTime = document.getElementById('recurring-return-time').value;
        const distance = document.getElementById('recurring-distance').value;

        if (!weekday || !departureTime || !returnTime || !distance) {
            alert('Please fill all the fields.');
            return;
        }

        const newRecurringTrip = {
            departure: weekday,
            departure_time: departureTime,
            return: weekday,
            return_time: returnTime,
            distance: parseInt(distance)
        };

        fetch('http://127.0.0.1:5000/add_recurring_trip', {
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
});
