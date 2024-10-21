"use client";
import { UserCredentials } from "../interfaces/general";
import { useRouter } from "next/navigation";

const LoginForm = () => {
    const router = useRouter();

    async function validateLogin(formData: FormData) {
        const creds: UserCredentials = {
            username: formData.get("username") as string,
            password: formData.get("password") as string,
        };

        const res = await fetch("/backend/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization:
                    // Encode into base64.
                    "Basic " + btoa(`${creds.username}:${creds.password}`),
            },
        });

        if (res.ok) {
            const data = await res.json();

            // Store the JWT token in local storage for future API calls to the backend.
            localStorage.setItem("access_token", data.access_token);

            router.push("/dashboard"); // Redirect to the dashboard after successful login.
        } else {
            // TODO: properly show an error message that authentication failed
            console.error("Authentication failed: ", res.statusText);
        }
    }

    return (
        <form className="space-y-4 w-2/5 ml-8" action={validateLogin}>
            <div className="text flex justify-start">
                <span className="italic font-semibold text-xl w-full text-left font-serif">
                    Begin Your Journey With Sentinel
                </span>
            </div>
            <div className="uname flex flex-col text-left">
                <label className="text-sm text-gray-500" htmlFor="username">
                    Username
                </label>
                <input
                    className="border-b-2 focus:outline-none"
                    type="text"
                    name="username"
                    placeholder="Admin"
                    required
                />
            </div>
            <div className="password flex flex-col text-left">
                <label className="text-sm text-gray-500" htmlFor="password">
                    Password
                </label>
                <input
                    className="border-b-2 focus:outline-none"
                    type="password"
                    name="password"
                    placeholder="************"
                    required
                />
            </div>
            <div className="submit-btn flex justify-end">
                <button
                    className="text-lg text-white bg-black rounded-xl py-1 px-3"
                    type="submit"
                >
                    Log In
                </button>
            </div>
        </form>
    );
};

export default LoginForm;
