import LoginForm from "./components/LoginForm";

export default function Home() {
    return (
        <div className="wrapper w-screen h-screen flex">
            <div className="left-icon w-1/2 border-2 flex justify-center">
                <h1 className="m-auto text-2xl">page icon here</h1>
            </div>
            <div className="login-form w-1/2 flex justify-start text-center m-auto">
                <LoginForm />
            </div>
        </div>
    );
}
